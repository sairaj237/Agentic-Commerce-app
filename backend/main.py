import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.api import router as api_router
from tasks import sweep_expired_orders

app = FastAPI(title="Agentic Cafe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Start the background cron job for sweeping expired orders
    asyncio.create_task(sweep_expired_orders())

# Include all modularized routes
app.include_router(api_router)
