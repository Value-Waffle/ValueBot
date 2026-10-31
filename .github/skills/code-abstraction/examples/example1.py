# --- BEFORE: Monolithic Business & DB Mix ---
# order_service.py
def process_checkout(user_id, cart_items):
    # Raw database queries mixed with mathematical pricing rules
    user = db.query("SELECT * FROM users WHERE id = %s", user_id)
    subtotal = sum(item['price'] * item['qty'] for item in cart_items)
    
    # Complex business calculation tied directly to database state
    discount = 0.0
    if user['is_premium'] and subtotal > 100:
        discount = subtotal * 0.15
        
    final_total = subtotal - discount
    db.execute("INSERT INTO receipts (user_id, total) VALUES (%s, %s)", user_id, final_total)


# --- AFTER: Abstracted Domain Engine ---
# loyalty_engine.py (Pure Logical Domain)
def calculate_discount(is_premium: bool, subtotal: float) -> float:
    """Isolated pricing rules. 100% blind to databases or SQL drivers."""
    if is_premium and subtotal > 100.0:
        return subtotal * 0.15
    return 0.0

# order_service.py (Orchestration & Storage Layer)
def process_checkout(user_id, cart_items):
    user = db.query("SELECT * FROM users WHERE id = %s", user_id)
    subtotal = sum(item['price'] * item['qty'] for item in cart_items)
    
    # Pure business boundary crossing
    discount = calculate_discount(user['is_premium'], subtotal)
    
    db.execute("INSERT INTO receipts (user_id, total) VALUES (%s, %s)", user_id, subtotal - discount)