import os
from datetime import datetime
from dotenv import load_dotenv
import razorpay

# Load env vars from .env
load_dotenv()

# --- Configuration & Logging ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgresql+psycopg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
MAX_TRANSACTION_LIMIT = 500.0

def audit_log(action: str, details: str):
    with open("audit_log.txt", "a") as f:
        f.write(f"[{datetime.now().isoformat()}] {action}: {details}\n")

def gatekeeper_check(amount: float):
    if amount > MAX_TRANSACTION_LIMIT:
        audit_log("GATEKEEPER_BLOCKED", f"Transaction of {amount} exceeds limit of {MAX_TRANSACTION_LIMIT}")
        return False
    return True
