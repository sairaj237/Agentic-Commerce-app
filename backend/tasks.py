import asyncio
from datetime import datetime, timedelta
from models import SessionLocal, Product, Order, OrderItem
from config import audit_log

async def sweep_expired_orders():
    """Background task to cancel abandoned orders and restock inventory."""
    while True:
        try:
            db = SessionLocal()
            threshold = datetime.utcnow() - timedelta(minutes=1)
            orders = db.query(Order).filter(Order.status == "PENDING").all()
            for order in orders:
                created_at = datetime.fromisoformat(order.created_at)
                if created_at < threshold:
                    order.status = "CANCELLED"
                    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
                    p_ids = [item.product_id for item in items]
                    if p_ids:
                        products = db.query(Product).filter(Product.id.in_(p_ids)).with_for_update().all()
                        pmap = {p.id: p for p in products}
                        for item in items:
                            if item.product_id in pmap:
                                pmap[item.product_id].inventory += item.quantity
                    db.commit()
                    audit_log("ORDER_CANCELLED", f"Order {order.id} expired (1 min). Inventory restored.")
            db.close()
        except Exception as e:
            print(f"Sweep error: {e}")
        await asyncio.sleep(20)
