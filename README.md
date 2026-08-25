# Agentic Commerce MVP 🛍️🤖

An End-to-End Agentic Commerce application that makes a merchant fully transactable by an AI buyer or user. Built with FastAPI, LangGraph, React, and Razorpay. 

The AI agent is capable of conversing with the user, querying a catalog, dynamically building a cart, and processing a secure, gated checkout via Razorpay's Test APIs.

## 🌟 Features
- **Conversational Checkout**: Order items via natural language (e.g., "I'd like to buy a coffee"). The AI automatically infers the Product ID and adds it to the cart.
- **End-to-End Razorpay Integration**: Automatically triggers the official Razorpay checkout modal directly in the React frontend based on the AI's backend tool calls.
- **Production-Grade Order Management System (OMS)**: Uses PostgreSQL Row-Level Locking (`with_for_update()`) to guarantee race-condition proof inventory tracking.
- **Modular Architecture**: Clean separation of concerns across `config.py`, `agent.py`, `tasks.py`, and `routers/api.py`.
- **Session Management**: Uses LangGraph's PostgreSQL Checkpointer (`PostgresSaver`) to fully isolate memory and cart state per user `session_id`.
- **Security & Gatekeeping**: A strict `MAX_TRANSACTION_LIMIT` blocks the agent from initiating high-value transactions maliciously.
- **Audit Logging**: Every financial action (adds to cart, checkouts, and blocks) is explicitly logged in `audit_log.txt` for full explainability.

## 🛠️ Tech Stack
- **AI / LLM Orchestration**: LangGraph, LangChain, OpenRouter (`openrouter/free`).
- **Backend**: Python, FastAPI, PostgreSQL (SQLAlchemy).
- **Frontend**: React (Vite), Vanilla CSS, React-Markdown.
- **Payments**: Razorpay APIs (Backend Order Creation + Frontend Checkout.js).

---

## 🚀 Quick Start

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # (or .\venv\Scripts\activate on Windows)
pip install fastapi uvicorn requests python-dotenv langchain-core langchain-openai langgraph psycopg_pool razorpay sqlalchemy
```

**Environment Variables** (`backend/.env`):
```env
OPENROUTER_API_KEY=your_openrouter_key
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
```

**Initialize Database & Run**:
Make sure Docker is running, then execute:
```bash
docker-compose up -d
python -c "from models import Base, engine; Base.metadata.create_all(bind=engine)"
python database.py  # Seeds the PostgreSQL catalog
uvicorn main:app --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## 🧠 Architecture Overview

### The Agentic Loop
1. **Frontend Request**: The React app generates a unique UUID (`session_id`) and sends the user's message to the `/chat` endpoint.
2. **Dynamic Prompting**: FastAPI fetches the user's isolated cart from PostgreSQL and injects it directly into the Agent's system prompt.
3. **Graph Execution**: LangGraph invokes the `agent_node` (hitting OpenRouter via raw requests to preserve reasoning state).
4. **Tool Execution**: 
   - `get_catalog()`: Queries the PostgreSQL `products` table.
   - `add_to_cart()`: Safely adds items to the `cart_items` table linked to the `session_id`, optimistically checking inventory.
   - `initiate_checkout()`: Checks the gatekeeper limit. If passed, it hits the Razorpay API to generate an `order_id`. **Crucially, it uses PostgreSQL Row-Level Locking (`with_for_update()`) to atomically lock product rows, strictly verify inventory, and decrement stock.** It moves the items into a `PENDING` Order.
5. **UI Trigger**: The backend returns the `order_id`. The React frontend intercepts this, dynamically loads Razorpay's `checkout.js`, and launches the payment modal.

### The Production OMS & Async Background Tasks
- **Payment Verification**: When a user completes the payment, the frontend sends the payload to `POST /verify_payment`. The backend uses `razorpay.utility.verify_payment_signature` to cryptographically validate the payload before marking the Order as `PAID`.
- **Automated Abandonment Cleanup**: A FastAPI background task (`tasks.py`) runs asynchronously every 20 seconds. It sweeps the database for any `PENDING` orders older than 1 minute (shortened for testing). If found, it automatically marks the order as `CANCELLED` and safely restores the inventory back to the `products` table.

## 🛡️ Security & Explainability
All agent actions are logged to `backend/audit_log.txt`. 
Example Audit Trail:
```text
[2026-08-21T19:50:00] ADD_TO_CART: [session-123] Added 1x Coffee
[2026-08-21T19:53:00] CHECKOUT_SUCCESS: [session-123] Created Razorpay order order_123 for 150.0 INR
[2026-08-21T20:10:00] GATEKEEPER_BLOCKED: Transaction of 1250 exceeds limit of 500.0
```

## Future Enhancements
If we were to take this MVP to a true enterprise-scale production environment, the following harness features would be implemented:
1. **Time-Travel Debugging & State Replay**: Leveraging LangGraph's `PostgresSaver` to build an admin UI that can step backward through any user's chat history to debug exactly why an LLM made a specific decision.
2. **Automated Evaluation Datasets (Evals)**: Building a `pytest` harness with 500+ simulated conversations to run regression testing against the Gatekeeper before any prompt or model upgrades.
3. **Fault-Tolerant Tool Wrappers**: Wrapping the Razorpay API tools in `Temporal.io` to automatically handle exponential backoffs if the payment gateway experiences downtime during checkout.
4. **Decision-Trace Auditing**: Storing the LLM's full "Reasoning Trace" (inner monologue) tied directly to the `order_id` for financial compliance auditing. **Cost-Optimized Solution:** Integrating dedicated LLM observability platforms like **Langfuse** or **LangSmith** instead of expensive data warehouses to provide built-in trace storage, session tagging, and cost-tracking out of the box for a fraction of the cost.
5. **True Server-to-Server Webhooks**: Replacing the frontend-driven `/verify_payment` with a secure Ngrok-backed webhook to completely isolate payment verification from client-side manipulation.
