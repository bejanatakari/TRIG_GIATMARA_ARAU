"""
TRIG PROFESSIONAL - AUTO WORKSHOP MANAGEMENT & POS SYSTEM
GM GEAR ARAU
Database Module: SQLite WAL Mode with ACID Transactions and Full Schema
"""

import sqlite3
import os
import json
import hashlib
import secrets
import datetime
from typing import Optional, List, Dict, Any, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trig_pos.db")

def get_db_connection() -> sqlite3.Connection:
    """Get a thread-safe connection to the SQLite database with WAL mode."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Secure password hashing using PBKDF2-HMAC-SHA256."""
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return dk.hex(), salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify password against stored hash."""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return secrets.compare_digest(dk.hex(), password_hash)

def init_db():
    """Initialize complete database schema with tables, constraints, and indexes."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Company Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS company_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        company_name TEXT NOT NULL DEFAULT 'GM GEAR ARAU',
        trading_name TEXT DEFAULT 'GM GEAR ARAU (Automotive Specialist)',
        reg_no TEXT DEFAULT '202403123456 (003123456-X)',
        phone TEXT DEFAULT '019-4567890',
        email TEXT DEFAULT 'gmgearkubangpasu@gmail.com',
        address TEXT DEFAULT 'No. 12, Jalan Arau Indah, 02600 Arau, Perlis',
        currency TEXT DEFAULT 'RM',
        tax_enabled INTEGER DEFAULT 0,
        tax_rate REAL DEFAULT 6.0,
        invoice_prefix TEXT DEFAULT 'INV-2026-',
        job_prefix TEXT DEFAULT 'JOB-2026-',
        receipt_prefix TEXT DEFAULT 'RCP-2026-',
        quote_prefix TEXT DEFAULT 'QUO-2026-',
        invoice_footer TEXT DEFAULT 'Terima kasih atas sokongan anda. Waranti 3 bulan atau 5,000km untuk alat ganti & upah mekanikal.',
        receipt_footer TEXT DEFAULT 'Simpan resit ini sebagai bukti pembayaran rasmi GM GEAR ARAU.',
        low_stock_threshold INTEGER DEFAULT 5,
        logo_base64 TEXT DEFAULT '',
        setup_completed INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Users & Roles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('ADMIN', 'CASHIER', 'MECHANIC')),
        phone TEXT,
        pin_hash TEXT,
        is_active INTEGER DEFAULT 1,
        last_login TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # 4. Customers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        ic_company TEXT,
        phone TEXT NOT NULL,
        whatsapp TEXT,
        email TEXT,
        address TEXT,
        notes TEXT,
        status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ARCHIVED')),
        is_demo INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. Vehicles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        vehicle_type TEXT NOT NULL CHECK (vehicle_type IN ('CAR', 'MOTORCYCLE', 'OTHER')),
        reg_no TEXT UNIQUE NOT NULL,
        make TEXT NOT NULL,
        model TEXT NOT NULL,
        variant TEXT,
        year INTEGER,
        engine TEXT,
        engine_cc INTEGER,
        engine_no TEXT,
        chassis_vin TEXT,
        transmission TEXT,
        mileage INTEGER DEFAULT 0,
        colour TEXT,
        colour_code TEXT,
        fuel_type TEXT,
        notes TEXT,
        status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ARCHIVED')),
        is_demo INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT
    );
    """)

    # 6. Suppliers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        notes TEXT,
        status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ARCHIVED')),
        is_demo INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 7. Inventory
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT UNIQUE NOT NULL,
        qr_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        brand TEXT,
        supplier_id INTEGER,
        cost_price REAL NOT NULL DEFAULT 0.0,
        selling_price REAL NOT NULL DEFAULT 0.0,
        stock_qty REAL NOT NULL DEFAULT 0.0,
        min_stock REAL NOT NULL DEFAULT 5.0,
        reorder_qty REAL NOT NULL DEFAULT 10.0,
        location TEXT,
        unit TEXT NOT NULL DEFAULT 'PCS',
        notes TEXT,
        status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ARCHIVED')),
        is_demo INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
    );
    """)

    # 8. Stock Movements (Stock Ledger)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventory_id INTEGER NOT NULL,
        qty REAL NOT NULL,
        movement_type TEXT NOT NULL CHECK (movement_type IN ('IN', 'OUT', 'ADJUSTMENT', 'RETURN')),
        before_qty REAL NOT NULL,
        after_qty REAL NOT NULL,
        user_id INTEGER,
        reference_type TEXT CHECK (reference_type IN ('JOB', 'INVOICE', 'PURCHASE', 'MANUAL', 'CANCEL_INVOICE')),
        reference_id TEXT,
        reason TEXT,
        is_demo INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE RESTRICT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 9. Quotations & Lines
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_no TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL,
        vehicle_id INTEGER NOT NULL,
        service_type TEXT NOT NULL CHECK (service_type IN ('AUTO_SERVICE', 'BODY_PAINT', 'MOTORCYCLE')),
        subtotal REAL NOT NULL DEFAULT 0.0,
        discount REAL NOT NULL DEFAULT 0.0,
        tax REAL NOT NULL DEFAULT 0.0,
        total REAL NOT NULL DEFAULT 0.0,
        validity_date TEXT,
        status TEXT DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'EXPIRED')),
        notes TEXT,
        is_demo INTEGER DEFAULT 0,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE RESTRICT,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotation_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quotation_id INTEGER NOT NULL,
        item_type TEXT NOT NULL CHECK (item_type IN ('PART', 'MATERIAL', 'LABOUR')),
        inventory_id INTEGER,
        sku TEXT,
        description TEXT NOT NULL,
        qty REAL NOT NULL DEFAULT 1.0,
        unit_price REAL NOT NULL DEFAULT 0.0,
        amount REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE SET NULL
    );
    """)

    # 10. Jobs (Work Orders)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_no TEXT UNIQUE NOT NULL,
        service_type TEXT NOT NULL CHECK (service_type IN ('AUTO_SERVICE', 'BODY_PAINT', 'MOTORCYCLE')),
        customer_id INTEGER NOT NULL,
        vehicle_id INTEGER NOT NULL,
        mileage INTEGER DEFAULT 0,
        complaint TEXT,
        inspection TEXT,
        diagnosis TEXT,
        recommendation TEXT,
        technician_id INTEGER,
        status TEXT NOT NULL DEFAULT 'IN_PROGRESS',
        estimated_completion TEXT,
        actual_completion TEXT,
        parts_total REAL DEFAULT 0.0,
        materials_total REAL DEFAULT 0.0,
        labour_total REAL DEFAULT 0.0,
        discount REAL DEFAULT 0.0,
        estimated_total REAL DEFAULT 0.0,
        notes TEXT,
        damage_description TEXT,
        repair_method TEXT,
        paint_colour TEXT,
        paint_code TEXT,
        damaged_panels TEXT,
        damage_types TEXT,
        paint_quantity REAL DEFAULT 0.0,
        estimated_days INTEGER DEFAULT 1,
        is_demo INTEGER DEFAULT 0,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE RESTRICT,
        FOREIGN KEY (technician_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 11. Job Items (Parts, Materials, Labour)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        item_type TEXT NOT NULL CHECK (item_type IN ('PART', 'MATERIAL', 'LABOUR')),
        inventory_id INTEGER,
        sku TEXT,
        name TEXT NOT NULL,
        qty REAL NOT NULL DEFAULT 1.0,
        unit_price REAL NOT NULL DEFAULT 0.0,
        amount REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE SET NULL
    );
    """)

    # 12. Job Images (Before, During, After photos for Body & Paint)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        stage TEXT NOT NULL CHECK (stage IN ('BEFORE', 'DURING', 'AFTER')),
        image_base64 TEXT NOT NULL,
        caption TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    );
    """)

    # 13. Invoices
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT UNIQUE NOT NULL,
        job_id INTEGER,
        customer_id INTEGER NOT NULL,
        vehicle_id INTEGER NOT NULL,
        service_type TEXT NOT NULL CHECK (service_type IN ('AUTO_SERVICE', 'BODY_PAINT', 'MOTORCYCLE')),
        subtotal REAL NOT NULL DEFAULT 0.0,
        discount REAL NOT NULL DEFAULT 0.0,
        tax REAL NOT NULL DEFAULT 0.0,
        grand_total REAL NOT NULL DEFAULT 0.0,
        deposit_amount REAL NOT NULL DEFAULT 0.0,
        paid_amount REAL NOT NULL DEFAULT 0.0,
        balance_due REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'APPROVED', 'PARTIALLY_PAID', 'PAID', 'CANCELLED')),
        qr_token TEXT UNIQUE NOT NULL,
        notes TEXT,
        approved_at TEXT,
        approved_by INTEGER,
        cancelled_at TEXT,
        cancelled_by INTEGER,
        cancel_reason TEXT,
        is_demo INTEGER DEFAULT 0,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE RESTRICT,
        FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (cancelled_by) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 14. Invoice Lines
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoice_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        item_type TEXT NOT NULL CHECK (item_type IN ('PART', 'MATERIAL', 'LABOUR')),
        inventory_id INTEGER,
        sku TEXT,
        description TEXT NOT NULL,
        qty REAL NOT NULL DEFAULT 1.0,
        unit_price REAL NOT NULL DEFAULT 0.0,
        amount REAL NOT NULL DEFAULT 0.0,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE SET NULL
    );
    """)

    # 15. Payments
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_no TEXT UNIQUE NOT NULL,
        invoice_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        payment_method TEXT NOT NULL CHECK (payment_method IN ('CASH', 'DUITNOW_QR', 'BANK_TRANSFER', 'CARD', 'E_WALLET', 'OTHER')),
        payment_type TEXT NOT NULL CHECK (payment_type IN ('DEPOSIT', 'PARTIAL', 'FINAL')),
        reference_no TEXT,
        notes TEXT,
        is_demo INTEGER DEFAULT 0,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 16. Receipts
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_no TEXT UNIQUE NOT NULL,
        payment_id INTEGER NOT NULL,
        invoice_id INTEGER NOT NULL,
        receipt_type TEXT NOT NULL CHECK (receipt_type IN ('DEPOSIT', 'PARTIAL', 'FINAL')),
        data_snapshot TEXT NOT NULL,
        is_demo INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT
    );
    """)

    # 17. Purchases (Supplier POs)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_no TEXT UNIQUE NOT NULL,
        supplier_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'ORDERED' CHECK (status IN ('ORDERED', 'RECEIVED', 'CANCELLED')),
        total_cost REAL NOT NULL DEFAULT 0.0,
        received_at TEXT,
        is_demo INTEGER DEFAULT 0,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id INTEGER NOT NULL,
        inventory_id INTEGER NOT NULL,
        qty REAL NOT NULL,
        cost_price REAL NOT NULL,
        amount REAL NOT NULL,
        FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_id) REFERENCES inventory(id) ON DELETE RESTRICT
    );
    """)

    # 18. Service Reminders
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS service_reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        vehicle_id INTEGER NOT NULL,
        service_type TEXT NOT NULL,
        last_service_date TEXT,
        next_service_date TEXT,
        next_mileage INTEGER,
        status TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'NOTIFIED', 'COMPLETED')),
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
    );
    """)

    # 19. Cashier Daily Closings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cashier_closings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        closing_date TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        opening_cash REAL NOT NULL DEFAULT 0.0,
        cash_collected REAL NOT NULL DEFAULT 0.0,
        non_cash_collected REAL NOT NULL DEFAULT 0.0,
        total_collected REAL NOT NULL DEFAULT 0.0,
        expected_cash REAL NOT NULL DEFAULT 0.0,
        actual_cash REAL NOT NULL DEFAULT 0.0,
        difference REAL NOT NULL DEFAULT 0.0,
        status TEXT DEFAULT 'CLOSED' CHECK (status IN ('OPEN', 'CLOSED')),
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
    );
    """)

    # 20. Audit Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_name TEXT,
        role TEXT,
        action TEXT NOT NULL,
        module TEXT NOT NULL,
        record_id TEXT,
        prev_value TEXT,
        new_value TEXT,
        ip_address TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Default company settings
    cursor.execute("SELECT COUNT(*) FROM company_settings WHERE id = 1;")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO company_settings (id) VALUES (1);")

    # Indices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_reg ON vehicles(reg_no);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_sku ON inventory(sku);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_qr ON inventory(qr_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_service ON jobs(service_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_qr ON invoices(qr_token);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_inventory ON stock_movements(inventory_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);")

    conn.commit()
    conn.close()

def log_audit(user: Optional[Dict[str, Any]], action: str, module: str, record_id: str, prev_val: Any = None, new_val: Any = None, ip: str = "127.0.0.1"):
    """Record an immutable audit log entry."""
    conn = get_db_connection()
    try:
        user_id = user.get("id") if user else None
        user_name = user.get("name") if user else "SYSTEM"
        role = user.get("role") if user else "SYSTEM"

        prev_str = json.dumps(prev_val, ensure_ascii=False) if prev_val is not None else None
        new_str = json.dumps(new_val, ensure_ascii=False) if new_val is not None else None

        conn.execute("""
            INSERT INTO audit_logs (user_id, user_name, role, action, module, record_id, prev_value, new_value, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (user_id, user_name, role, action, module, str(record_id), prev_str, new_str, ip))
        conn.commit()
    finally:
        conn.close()

# Auto initialize
init_db()
