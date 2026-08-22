from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage
from models import SessionLocal, CartItem, Product, Order
from agent import compiled_graph, pending_checkouts
from config import rzp_client, audit_log, RAZORPAY_KEY_ID

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: str

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

def get_cart_for_session(session_id: str):
    db = SessionLocal()
    cart_items = db.query(CartItem, Product).join(Product, CartItem.product_id == Product.id).filter(CartItem.session_id == session_id).all()
    
    cart_list = []
    for item, product in cart_items:
        cart_list.append({
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "quantity": item.quantity
        })
    db.close()
    return cart_list

@router.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id
    
    # Get current cart state for this session
    user_cart = get_cart_for_session(session_id)
    cart_summary = ", ".join([f"{item['quantity']}x {item['name']} (₹{item['price']})" for item in user_cart])
    if not cart_summary:
        cart_summary = "Empty"

    system_prompt = (
        "You are an Agentic Commerce assistant for a cafe. Your goal is to help the user order, "
        "upsell politely, and process checkout. "
        "IMPORTANT: When a user wants to buy something, use your 'get_catalog' tool to find the item. "
        "NEVER ask the user for a product ID or quantity if they just name the item (e.g. 'coffee'); "
        "infer the ID from the catalog and assume a quantity of 1 unless specified. "
        "Use tools to add items to the cart. "
        "CRITICAL: NEVER call the initiate_checkout tool until you have explicitly asked the user if they are ready to checkout and they have confirmed. "
        "If the user asks to check their order or payment status, use the check_order_status tool. "
        "Always use the Indian Rupee symbol (₹) for all prices and never use the dollar sign ($). "
        f"CURRENT CART CONTENTS: {cart_summary}. Calculate the total amount yourself from these contents before calling initiate_checkout."
    )
    
    inputs = {
        "messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=request.message)
        ]
    }
    
    try:
        # Pass thread_id into the configurable block
        config = {"configurable": {"thread_id": session_id}}
        final_state = compiled_graph.invoke(inputs, config=config)
        
        # Refetch cart in case the agent modified it during execution
        updated_cart = get_cart_for_session(session_id)
        
        # Check if a checkout was initiated during this request
        checkout_payload = None
        if session_id in pending_checkouts:
            checkout_payload = pending_checkouts.pop(session_id)
            checkout_payload["key_id"] = RAZORPAY_KEY_ID
            
        return {
            "reply": final_state["messages"][-1].content,
            "cart": updated_cart,
            "checkout": checkout_payload
        }
    except Exception as e:
        return {"reply": f"Agent encountered an error: {str(e)}", "cart": []}

@router.post("/verify_payment")
def verify_payment(req: VerifyPaymentRequest):
    try:
        rzp_client.utility.verify_payment_signature({
            'razorpay_order_id': req.razorpay_order_id,
            'razorpay_payment_id': req.razorpay_payment_id,
            'razorpay_signature': req.razorpay_signature
        })
        db = SessionLocal()
        order = db.query(Order).filter(Order.id == req.razorpay_order_id).first()
        if order:
            order.status = "PAID"
            db.commit()
            audit_log("ORDER_PAID", f"Order {order.id} paid successfully.")
        db.close()
        return {"status": "success"}
    except Exception as e:
        audit_log("PAYMENT_VERIFICATION_FAILED", str(e))
        raise HTTPException(status_code=400, detail="Invalid signature")
