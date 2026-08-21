from models import SessionLocal, engine, Base, Product

# Drop all tables first so we can cleanly add the new inventory column
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def seed_db():
    db = SessionLocal()
    # Check if we already seeded
    if db.query(Product).count() == 0:
        products = [
            Product(name="Coffee", category="Beverage", price=150.0, inventory=100),
            Product(name="Espresso", category="Beverage", price=100.0, inventory=100),
            Product(name="Pastry", category="Food", price=200.0, inventory=100),
            Product(name="Sandwich", category="Food", price=250.0, inventory=100),
            Product(name="Special Rare Cookie", category="Food", price=50.0, inventory=1),
        ]
        db.add_all(products)
        db.commit()
    db.close()

if __name__ == "__main__":
    seed_db()
    print("Database seeded.")
