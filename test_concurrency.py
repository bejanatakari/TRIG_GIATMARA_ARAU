"""
TRIG PROFESSIONAL - Concurrency Stress Test
Verifies that 5 simultaneous threads cannot double-deduct stock or overpay an invoice.
"""

import threading
import time
from database import get_db_connection
import business_logic

def test_concurrent_invoice_approval():
    conn = get_db_connection()
    c = conn.cursor()
    # Create test invoice in draft with 1 item
    c.execute("""
        INSERT INTO invoices (invoice_no, customer_id, vehicle_id, service_type, subtotal, grand_total, balance_due, status, qr_token)
        VALUES ('INV-CONCUR-001', 1, 1, 'AUTO_SERVICE', 168.0, 168.0, 168.0, 'DRAFT', 'TOKEN-CONCUR-1');
    """)
    inv_id = c.lastrowid
    # Part item with inventory_id 1
    c.execute("""
        INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount)
        VALUES (?, 'PART', 1, 'OIL-SYN-5W40', 'Petronas 5W40', 1, 168.0, 168.0);
    """, (inv_id,))
    
    # Get current stock
    c.execute("SELECT stock_qty FROM inventory WHERE id = 1;")
    initial_stock = float(c.fetchone()[0])
    conn.commit()
    conn.close()

    user = {"id": 1, "name": "Admin Tester", "role": "ADMIN"}
    results = []

    def attempt_approval():
        res = business_logic.approve_invoice_transaction(inv_id, user)
        results.append(res)

    # 5 simultaneous threads
    threads = [threading.Thread(target=attempt_approval) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Check stock after 5 concurrent attempts
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT stock_qty FROM inventory WHERE id = 1;")
    final_stock = float(c.fetchone()[0])
    conn.close()

    stock_diff = initial_stock - final_stock
    print(f"Initial Stock: {initial_stock}, Final Stock: {final_stock}, Diff: {stock_diff}")
    assert stock_diff == 1.0, f"Stock deducted {stock_diff} times instead of exactly 1.0!"
    print("CONCURRENCY TEST PASSED: Stock was deducted EXACTLY ONCE across 5 simultaneous threads!")

if __name__ == "__main__":
    test_concurrent_invoice_approval()
