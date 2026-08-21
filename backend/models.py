from sqlalchemy import Column, Integer, String, Float, Boolean
import os
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL is not set in .env")

# Ensure it uses psycopg adapter
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Float)
    inventory = Column(Integer, default=0)
    currency = Column(String, default="INR")
    category = Column(String, index=True)

from datetime import datetime

class CartItem(Base):
    __tablename__ = "cart_items"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    product_id = Column(Integer)
    quantity = Column(Integer, default=1)

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(String, primary_key=True, index=True) # razorpay_order_id
    session_id = Column(String, index=True)
    status = Column(String, default="PENDING")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, index=True)
    product_id = Column(Integer)
    quantity = Column(Integer)
