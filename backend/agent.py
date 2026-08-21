import json
import requests
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_core.runnables import RunnableConfig

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from models import SessionLocal, Product, CartItem, Order, OrderItem
from config import (
    OPENROUTER_API_KEY, 
    rzp_client, 
    DATABASE_URL, 
    gatekeeper_check, 
    audit_log,
    MAX_TRANSACTION_LIMIT
)

# --- LangChain Tools ---
@tool
def get_catalog():
    """Get a list of all available products and their prices."""
    db = SessionLocal()
    products = db.query(Product).all()
    catalog = [{"id": p.id, "name": p.name, "price": p.price, "category": p.category} for p in products]
    db.close()
    return json.dumps(catalog)

@tool
def add_to_cart(product_id: int, quantity: int, config: RunnableConfig):
    """Add an item to the user's cart."""
    session_id = config.get("configurable", {}).get("thread_id")
    if not session_id:
        return "Error: Missing session ID."
        
    db = SessionLocal()
    product = db.query(Product).filter(Product.id == product_id).first()
    
    if product:
        # Optimistic check (no lock)
        current_in_cart = 0
        cart_item = db.query(CartItem).filter(CartItem.session_id == session_id, CartItem.product_id == product_id).first()
        if cart_item:
            current_in_cart = cart_item.quantity
            
        if product.inventory < (current_in_cart + quantity):
            db.close()
            return f"Failed: We only have {product.inventory} of {product.name} in stock, but you requested {current_in_cart + quantity} total."

        if cart_item:
            cart_item.quantity += quantity
        else:
            cart_item = CartItem(session_id=session_id, product_id=product_id, quantity=quantity)
            db.add(cart_item)
        db.commit()
        audit_log("ADD_TO_CART", f"[{session_id}] Added {quantity}x {product.name}")
        res = f"Successfully added {quantity} of {product.name} to cart."
    else:
        res = "Product not found."
    db.close()
    return res

pending_checkouts = {}

@tool
def initiate_checkout(total_amount: float, config: RunnableConfig):
    """Initiate checkout for the items in the cart. Returns a payment order ID or failure reason."""
    session_id = config.get("configurable", {}).get("thread_id")
    
    if not gatekeeper_check(total_amount):
        res = f"Checkout failed: Amount exceeds pre-authorized limit of {MAX_TRANSACTION_LIMIT} INR."
        audit_log("CHECKOUT_REJECTED", f"[{session_id}] {res}")
        return res
        
    db = SessionLocal()
    try:
        # 1. Fetch Cart Items
        cart_items = db.query(CartItem).filter(CartItem.session_id == session_id).all()
        if not cart_items:
            db.close()
            return "Checkout failed: Cart is empty."
            
        # 2. Lock the associated Products (Row-Level Lock)
        product_ids = [item.product_id for item in cart_items]
        locked_products = db.query(Product).filter(Product.id.in_(product_ids)).with_for_update().all()
        
        # 3. Verify Inventory Under Lock
        product_map = {p.id: p for p in locked_products}
        for item in cart_items:
            product = product_map.get(item.product_id)
            if not product or product.inventory < item.quantity:
                db.rollback()
                db.close()
                res = f"Checkout failed: Insufficient stock for {product.name if product else 'item'}. Only {product.inventory if product else 0} left."
                audit_log("CHECKOUT_REJECTED", f"[{session_id}] {res}")
                return res
        
        # 4. Process Payment Gateway
        order_data = {
            "amount": int(total_amount * 100),
            "currency": "INR",
            "receipt": f"receipt_{session_id[:8]}"
        }
        order = rzp_client.order.create(data=order_data)
        
        # 5. Create Order, OrderItems, Decrement Inventory & Clear Cart
        order_record = Order(id=order['id'], session_id=session_id, status="PENDING")
        db.add(order_record)
        
        for item in cart_items:
            product = product_map[item.product_id]
            product.inventory -= item.quantity
            db.add(OrderItem(order_id=order['id'], product_id=product.id, quantity=item.quantity))
            db.delete(item)
            
        pending_checkouts[session_id] = {
            "order_id": order['id'],
            "amount": order_data['amount'],
            "currency": "INR"
        }
        
        db.commit() # Commits transaction & releases locks
        db.close()
        
        res = f"Checkout initiated successfully. Order ID: {order['id']}"
        audit_log("CHECKOUT_SUCCESS", f"[{session_id}] Created Razorpay order {order['id']} for {total_amount} INR")
        return res
    except Exception as e:
        db.rollback()
        db.close()
        res = f"Checkout failed due to error: {str(e)}"
        audit_log("CHECKOUT_ERROR", f"[{session_id}] {str(e)}")
        return res

tools = [get_catalog, add_to_cart, initiate_checkout]
openrouter_tools = [convert_to_openai_tool(t) for t in tools]

# --- LangGraph Setup ---
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

def agent_node(state: AgentState):
    # Convert state messages to openrouter format
    messages_json = []
    for msg in state["messages"]:
        if isinstance(msg, SystemMessage):
            messages_json.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            messages_json.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            m = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                m["tool_calls"] = []
                for tc in msg.tool_calls:
                    m["tool_calls"].append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"])
                        }
                    })
            if "reasoning_details" in msg.additional_kwargs:
                m["reasoning_details"] = msg.additional_kwargs["reasoning_details"]
            messages_json.append(m)
        elif isinstance(msg, ToolMessage):
            messages_json.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content,
                "name": msg.name
            })

    # Call OpenRouter
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": "openrouter/free",
            "messages": messages_json,
            "tools": openrouter_tools,
            "reasoning": {"enabled": True}
        })
    )
    
    resp_data = response.json()
    if "choices" not in resp_data:
        raise Exception(f"OpenRouter Error: {resp_data}")
        
    message_data = resp_data["choices"][0]["message"]
    
    # Parse back to Langchain AIMessage
    ai_kwargs = {}
    if "reasoning_details" in message_data:
         ai_kwargs["reasoning_details"] = message_data["reasoning_details"]
         
    tool_calls = []
    if "tool_calls" in message_data and message_data["tool_calls"]:
        for tc in message_data["tool_calls"]:
            tool_calls.append({
                "name": tc["function"]["name"],
                "args": json.loads(tc["function"]["arguments"]),
                "id": tc["id"]
            })
            
    return {"messages": [AIMessage(
        content=message_data.get("content") or "",
        tool_calls=tool_calls,
        additional_kwargs=ai_kwargs
    )]}

tool_node = ToolNode(tools)

# Create the graph and attach the Postgres checkpointer
workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", tools_condition)
workflow.add_edge("tools", "agent")

# Use Postgres checkpointer for persisting states globally
connection_pool = ConnectionPool(
    conninfo=DATABASE_URL,
    max_size=20,
    kwargs={"autocommit": True}
)
memory = PostgresSaver(connection_pool)
memory.setup() # Create checkpoint tables if they don't exist
compiled_graph = workflow.compile(checkpointer=memory)
