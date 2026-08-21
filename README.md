# Agentic Commerce MVP 🛍️🤖

An End-to-End Agentic Commerce application that makes a merchant fully transactable by an AI buyer or user. Built with FastAPI, LangGraph, React, and Razorpay. 

The AI agent is capable of conversing with the user, querying a catalog, dynamically building a cart, and processing a secure, gated checkout via Razorpay's Test APIs.

## 🌟 Features
- **Conversational Checkout**: Order items via natural language (e.g., "I'd like to buy a coffee"). The AI automatically infers the Product ID and adds it to the cart.
- **End-to-End Razorpay Integration**: Automatically triggers the official Razorpay checkout modal directly in the React frontend based on the AI's backend tool calls.
- **Production-Grade Session Management**: Uses LangGraph's PostgreSQL Checkpointer (`PostgresSaver`) and a custom `CartItem` database to fully isolate memory and cart state per user `session_id`.
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
pip install fastapi uvicorn requests python-dotenv langchain-core langchain-openai langgraph langgraph-checkpoint-sqlite razorpay sqlalchemy
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
2. **Dynamic Prompting**: FastAPI fetches the user's isolated cart from SQLite and injects it directly into the Agent's system prompt.
3. **Graph Execution**: LangGraph invokes the `agent_node` (hitting OpenRouter via raw requests to preserve reasoning state) and conditionally routes to the `tool_node` if tools are called.
4. **Tool Execution**: 
   - `get_catalog()`: Queries the PostgreSQL `products` table.
   - `add_to_cart()`: Safely adds items to the `cart_items` table linked to the `session_id`.
   - `initiate_checkout()`: Checks the gatekeeper limit. If passed, hits the Razorpay API to generate an `order_id` and saves it to a pending checkout pool.
5. **UI Trigger**: If a checkout is pending, the `/chat` endpoint attaches it to the JSON response. The React frontend intercepts this, dynamically loads Razorpay's `checkout.js`, and launches the payment modal over the chat.

## 🛡️ Security & Explainability
All agent actions are logged to `backend/audit_log.txt`. 
Example Audit Trail:
```text
[2026-08-21T19:50:00] ADD_TO_CART: [session-123] Added 1x Coffee
[2026-08-21T19:53:00] CHECKOUT_SUCCESS: [session-123] Created Razorpay order order_123 for 150.0 INR
[2026-08-21T20:10:00] GATEKEEPER_BLOCKED: Transaction of 1250 exceeds limit of 500.0
```
