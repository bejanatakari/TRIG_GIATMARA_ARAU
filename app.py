"""
TRIG PROFESSIONAL - AUTO WORKSHOP MANAGEMENT & POS SYSTEM
GM GEAR ARAU
Main Application Server: Concurrent REST API & Static File Server
Zero external runtime dependencies - Built on Python 3 Standard Library
"""

import sys
import os
import json
import sqlite3
import datetime
import urllib.parse
import secrets
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional, Dict, Any, List, Tuple

from database import get_db_connection, hash_password, verify_password, log_audit, DB_PATH
import business_logic

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PORT = 8080

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server supporting multiple concurrent clients."""
    daemon_threads = True

class TrigPOSHandler(SimpleHTTPRequestHandler):
    """Robust HTTP Request Handler supporting REST API, JSON endpoints, and SPA static assets."""

    def get_client_ip(self) -> str:
        client = self.client_address[0] if self.client_address else "127.0.0.1"
        return client

    def get_auth_user(self) -> Optional[Dict[str, Any]]:
        """Extract and validate session token from Authorization header or Cookie."""
        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[1].strip()
        elif "Cookie" in self.headers:
            cookies = self.headers["Cookie"].split(";")
            for c in cookies:
                parts = c.strip().split("=")
                if len(parts) == 2 and parts[0] == "session_token":
                    token = parts[1]
                    break

        if not token:
            return None

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.token, s.user_id, s.role, u.name, u.email, u.phone, u.is_active
                FROM sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token = ? AND datetime(s.expires_at) > datetime('now');
            """, (token,))
            row = cursor.fetchone()
            if row and row["is_active"] == 1:
                return {
                    "id": row["user_id"],
                    "token": row["token"],
                    "role": row["role"],
                    "name": row["name"],
                    "email": row["email"],
                    "phone": row["phone"]
                }
            return None
        finally:
            conn.close()

    def send_json(self, data: Any, status: int = 200, extra_headers: Optional[Dict[str, str]] = None):
        """Send JSON response with appropriate headers and status."""
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: int = 400):
        self.send_json({"success": False, "error": message}, status=status)

    def parse_json_body(self) -> Dict[str, Any]:
        """Parse incoming JSON payload safely."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                raw_body = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw_body)
            return {}
        except Exception as e:
            return {}

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    # =========================================================================
    # GET REQUEST ROUTER
    # =========================================================================
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)
        ip = self.get_client_ip()

        # Static assets
        if path == "/" or path == "/index.html":
            return self.serve_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
        elif path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            full_path = os.path.join(STATIC_DIR, rel_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                content_type = "text/plain"
                if full_path.endswith(".css"):
                    content_type = "text/css; charset=utf-8"
                elif full_path.endswith(".js"):
                    content_type = "application/javascript; charset=utf-8"
                elif full_path.endswith(".png"):
                    content_type = "image/png"
                elif full_path.endswith(".svg"):
                    content_type = "image/svg+xml"
                elif full_path.endswith(".ico"):
                    content_type = "image/x-icon"
                return self.serve_file(full_path, content_type)

        # Public API
        if path == "/api/company-info":
            return self.handle_get_company_info()

        # Auth check for protected APIs
        user = self.get_auth_user()
        if not user:
            return self.send_error_json("Sila log masuk terlebih dahulu untuk mengakses sistem.", 401)

        conn = get_db_connection()
        try:
            # 1. Auth Me
            if path == "/api/auth/me":
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM company_settings WHERE id = 1;")
                company = dict(cursor.fetchone() or {})
                return self.send_json({"success": True, "user": user, "company": company})

            # 2. Dashboard Stats & Charts
            elif path == "/api/dashboard/stats":
                return self.handle_dashboard_stats(conn, query)
            elif path == "/api/dashboard/charts":
                return self.handle_dashboard_charts(conn, query)

            # 3. Global Search
            elif path == "/api/global-search":
                q = query.get("q", [""])[0].strip()
                return self.handle_global_search(conn, q)

            # 4. Customers
            elif path == "/api/customers":
                search = query.get("search", [""])[0].strip()
                status = query.get("status", ["ACTIVE"])[0]
                cursor = conn.cursor()
                if search:
                    cursor.execute("""
                        SELECT * FROM customers
                        WHERE (name LIKE ? OR phone LIKE ? OR ic_company LIKE ?) AND status = ?
                        ORDER BY id DESC LIMIT 50;
                    """, (f"%{search}%", f"%{search}%", f"%{search}%", status))
                else:
                    cursor.execute("SELECT * FROM customers WHERE status = ? ORDER BY id DESC LIMIT 100;", (status,))
                rows = [dict(r) for r in cursor.fetchall()]
                return self.send_json({"success": True, "customers": rows})

            elif path.startswith("/api/customers/"):
                cust_id = int(path.split("/api/customers/")[1])
                return self.handle_customer_detail(conn, cust_id)

            # 5. Vehicles
            elif path == "/api/vehicles":
                search = query.get("search", [""])[0].strip()
                v_type = query.get("type", [""])[0].strip()
                cust_id = query.get("customer_id", [""])[0].strip()
                cursor = conn.cursor()

                conditions = ["v.status = 'ACTIVE'"]
                params = []
                if search:
                    conditions.append("(v.reg_no LIKE ? OR v.make LIKE ? OR v.model LIKE ? OR v.chassis_vin LIKE ?)")
                    params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
                if v_type:
                    conditions.append("v.vehicle_type = ?")
                    params.append(v_type)
                if cust_id:
                    conditions.append("v.customer_id = ?")
                    params.append(cust_id)

                where_clause = " AND ".join(conditions)
                cursor.execute(f"""
                    SELECT v.*, c.name as customer_name, c.phone as customer_phone
                    FROM vehicles v
                    JOIN customers c ON v.customer_id = c.id
                    WHERE {where_clause}
                    ORDER BY v.id DESC LIMIT 100;
                """, params)
                return self.send_json({"success": True, "vehicles": [dict(r) for r in cursor.fetchall()]})

            elif path.startswith("/api/vehicles/"):
                v_id = int(path.split("/api/vehicles/")[1])
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT v.*, c.name as customer_name, c.phone as customer_phone, c.address as customer_address
                    FROM vehicles v
                    JOIN customers c ON v.customer_id = c.id
                    WHERE v.id = ?;
                """, (v_id,))
                row = cursor.fetchone()
                if not row:
                    return self.send_error_json("Kenderaan tidak ditemui.", 404)
                return self.send_json({"success": True, "vehicle": dict(row)})

            # 6. Inventory & QR Lookup
            elif path == "/api/inventory/qr-lookup":
                code = query.get("code", [""])[0].strip()
                if not code:
                    return self.send_error_json("Kod QR atau SKU diperlukan.")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT i.*, s.company as supplier_name
                    FROM inventory i
                    LEFT JOIN suppliers s ON i.supplier_id = s.id
                    WHERE (i.qr_id = ? OR i.sku = ?) AND i.status = 'ACTIVE';
                """, (code, code))
                row = cursor.fetchone()
                if not row:
                    return self.send_error_json("Alat ganti tidak ditemui untuk kod ini.", 404)
                return self.send_json({"success": True, "item": dict(row)})

            elif path == "/api/inventory":
                search = query.get("search", [""])[0].strip()
                cat = query.get("category", [""])[0].strip()
                low_stock = query.get("low_stock", ["0"])[0] == "1"
                cursor = conn.cursor()

                conditions = ["i.status = 'ACTIVE'"]
                params = []
                if search:
                    conditions.append("(i.sku LIKE ? OR i.name LIKE ? OR i.brand LIKE ? OR i.location LIKE ?)")
                    params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
                if cat:
                    conditions.append("i.category = ?")
                    params.append(cat)
                if low_stock:
                    conditions.append("i.stock_qty <= i.min_stock")

                where_clause = " AND ".join(conditions)
                cursor.execute(f"""
                    SELECT i.*, s.company as supplier_name
                    FROM inventory i
                    LEFT JOIN suppliers s ON i.supplier_id = s.id
                    WHERE {where_clause}
                    ORDER BY i.name ASC;
                """, params)
                return self.send_json({"success": True, "inventory": [dict(r) for r in cursor.fetchall()]})

            elif path == "/api/stock-movements":
                inv_id = query.get("inventory_id", [""])[0]
                cursor = conn.cursor()
                if inv_id:
                    cursor.execute("""
                        SELECT sm.*, i.name as item_name, i.sku, u.name as user_name
                        FROM stock_movements sm
                        JOIN inventory i ON sm.inventory_id = i.id
                        LEFT JOIN users u ON sm.user_id = u.id
                        WHERE sm.inventory_id = ?
                        ORDER BY sm.id DESC LIMIT 100;
                    """, (inv_id,))
                else:
                    cursor.execute("""
                        SELECT sm.*, i.name as item_name, i.sku, u.name as user_name
                        FROM stock_movements sm
                        JOIN inventory i ON sm.inventory_id = i.id
                        LEFT JOIN users u ON sm.user_id = u.id
                        ORDER BY sm.id DESC LIMIT 100;
                    """)
                return self.send_json({"success": True, "movements": [dict(r) for r in cursor.fetchall()]})

            # 7. Quotations
            elif path == "/api/quotations":
                service_type = query.get("service_type", [""])[0]
                cursor = conn.cursor()
                params = []
                where = ""
                if service_type:
                    where = "WHERE q.service_type = ?"
                    params.append(service_type)
                cursor.execute(f"""
                    SELECT q.*, c.name as customer_name, c.phone as customer_phone,
                           v.reg_no as vehicle_reg, v.make as vehicle_make, v.model as vehicle_model
                    FROM quotations q
                    JOIN customers c ON q.customer_id = c.id
                    JOIN vehicles v ON q.vehicle_id = v.id
                    {where}
                    ORDER BY q.id DESC LIMIT 100;
                """, params)
                return self.send_json({"success": True, "quotations": [dict(r) for r in cursor.fetchall()]})

            elif path.startswith("/api/quotations/"):
                q_id = int(path.split("/api/quotations/")[1])
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT q.*, c.name as customer_name, c.phone as customer_phone, c.address as customer_address,
                           v.reg_no as vehicle_reg, v.make as vehicle_make, v.model as vehicle_model, v.mileage as vehicle_mileage,
                           u.name as creator_name
                    FROM quotations q
                    JOIN customers c ON q.customer_id = c.id
                    JOIN vehicles v ON q.vehicle_id = v.id
                    LEFT JOIN users u ON q.created_by = u.id
                    WHERE q.id = ?;
                """, (q_id,))
                quote = cursor.fetchone()
                if not quote:
                    return self.send_error_json("Sebut harga tidak ditemui.", 404)
                cursor.execute("SELECT * FROM quotation_lines WHERE quotation_id = ?;", (q_id,))
                lines = [dict(r) for r in cursor.fetchall()]
                res = dict(quote)
                res["lines"] = lines
                return self.send_json({"success": True, "quotation": res})

            # 8. Work Orders / Jobs
            elif path == "/api/jobs":
                service_type = query.get("service_type", [""])[0]
                status = query.get("status", [""])[0]
                mechanic_id = query.get("mechanic_id", [""])[0]

                # If logged-in user is MECHANIC, lock to assigned jobs unless specified
                if user["role"] == "MECHANIC":
                    mechanic_id = str(user["id"])

                conditions = []
                params = []
                if service_type:
                    conditions.append("j.service_type = ?")
                    params.append(service_type)
                if status:
                    conditions.append("j.status = ?")
                    params.append(status)
                if mechanic_id:
                    conditions.append("j.technician_id = ?")
                    params.append(mechanic_id)

                where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT j.*, c.name as customer_name, c.phone as customer_phone,
                           v.reg_no as vehicle_reg, v.make as vehicle_make, v.model as vehicle_model,
                           u.name as technician_name
                    FROM jobs j
                    JOIN customers c ON j.customer_id = c.id
                    JOIN vehicles v ON j.vehicle_id = v.id
                    LEFT JOIN users u ON j.technician_id = u.id
                    {where_clause}
                    ORDER BY j.id DESC LIMIT 100;
                """, params)
                return self.send_json({"success": True, "jobs": [dict(r) for r in cursor.fetchall()]})

            elif path.startswith("/api/jobs/"):
                subpath = path.split("/api/jobs/")[1]
                if "/images" in subpath:
                    job_id = int(subpath.split("/images")[0])
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, job_id, stage, caption, created_at, image_base64 FROM job_images WHERE job_id = ? ORDER BY id ASC;", (job_id,))
                    return self.send_json({"success": True, "images": [dict(r) for r in cursor.fetchall()]})

                job_id = int(subpath)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT j.*, c.name as customer_name, c.phone as customer_phone, c.address as customer_address,
                           v.reg_no as vehicle_reg, v.make as vehicle_make, v.model as vehicle_model, v.year as vehicle_year,
                           v.colour as vehicle_colour, v.colour_code as vehicle_colour_code, v.engine_no, v.chassis_vin,
                           u.name as technician_name
                    FROM jobs j
                    JOIN customers c ON j.customer_id = c.id
                    JOIN vehicles v ON j.vehicle_id = v.id
                    LEFT JOIN users u ON j.technician_id = u.id
                    WHERE j.id = ?;
                """, (job_id,))
                job = cursor.fetchone()
                if not job:
                    return self.send_error_json("Kad Kerja tidak ditemui.", 404)

                cursor.execute("SELECT * FROM job_items WHERE job_id = ? ORDER BY id ASC;", (job_id,))
                items = [dict(r) for r in cursor.fetchall()]
                cursor.execute("SELECT id, stage, caption, created_at, image_base64 FROM job_images WHERE job_id = ?;", (job_id,))
                images = [dict(r) for r in cursor.fetchall()]

                res = dict(job)
                res["items"] = items
                res["images"] = images
                return self.send_json({"success": True, "job": res})

            # 9. Invoices & QR Token Lookup
            elif path == "/api/invoices/qr-lookup":
                token = query.get("token", [""])[0].strip()
                if not token:
                    return self.send_error_json("Token QR invois diperlukan.")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT i.*, c.name as customer_name, c.phone as customer_phone,
                           v.reg_no as vehicle_reg, v.make as vehicle_make, v.model as vehicle_model
                    FROM invoices i
                    JOIN customers c ON i.customer_id = c.id
                    JOIN vehicles v ON i.vehicle_id = v.id
                    WHERE i.qr_token = ?;
                """, (token,))
                inv = cursor.fetchone()
                if not inv:
                    return self.send_error_json("Invois tidak sah atau tidak ditemui untuk kod QR ini.", 404)

                cursor.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?;", (inv["id"],))
                lines = [dict(r) for r in cursor.fetchall()]
                res = dict(inv)
                res["lines"] = lines
                return self.send_json({"success": True, "invoice": res})

            elif path == "/api/invoices":
                service_type = query.get("service_type", [""])[0]
                status = query.get("status", [""])[0]
                cursor = conn.cursor()

                conditions = []
                params = []
                if service_type:
                    conditions.append("i.service_type = ?")
                    params.append(service_type)
                if status:
                    conditions.append("i.status = ?")
                    params.append(status)

                where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
                cursor.execute(f"""
                    SELECT i.*, c.name as customer_name, c.phone as customer_phone,
                           v.reg_no as vehicle_reg, v.make as vehicle_make, v.model as vehicle_model,
                           j.job_no
                    FROM invoices i
                    JOIN customers c ON i.customer_id = c.id
                    JOIN vehicles v ON i.vehicle_id = v.id
                    LEFT JOIN jobs j ON i.job_id = j.id
                    {where}
                    ORDER BY i.id DESC LIMIT 100;
                """, params)
                return self.send_json({"success": True, "invoices": [dict(r) for r in cursor.fetchall()]})

            elif path.startswith("/api/invoices/"):
                inv_id = int(path.split("/api/invoices/")[1])
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT i.*, c.name as customer_name, c.phone as customer_phone, c.address as customer_address,
                           v.reg_no as vehicle_reg, v.make as vehicle_make, v.model as vehicle_model, v.mileage as vehicle_mileage,
                           j.job_no
                    FROM invoices i
                    JOIN customers c ON i.customer_id = c.id
                    JOIN vehicles v ON i.vehicle_id = v.id
                    LEFT JOIN jobs j ON i.job_id = j.id
                    WHERE i.id = ?;
                """, (inv_id,))
                inv = cursor.fetchone()
                if not inv:
                    return self.send_error_json("Invois tidak ditemui.", 404)

                cursor.execute("SELECT * FROM invoice_lines WHERE invoice_id = ?;", (inv_id,))
                lines = [dict(r) for r in cursor.fetchall()]
                cursor.execute("SELECT * FROM payments WHERE invoice_id = ? ORDER BY id ASC;", (inv_id,))
                payments = [dict(r) for r in cursor.fetchall()]

                res = dict(inv)
                res["lines"] = lines
                res["payments"] = payments
                return self.send_json({"success": True, "invoice": res})

            # 10. Receipts
            elif path == "/api/receipts":
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT r.*, p.amount, p.payment_method, p.created_at as payment_date,
                           i.invoice_no, i.service_type
                    FROM receipts r
                    JOIN payments p ON r.payment_id = p.id
                    JOIN invoices i ON r.invoice_id = i.id
                    ORDER BY r.id DESC LIMIT 100;
                """)
                return self.send_json({"success": True, "receipts": [dict(r) for r in cursor.fetchall()]})

            elif path.startswith("/api/receipts/"):
                param = path.split("/api/receipts/")[1]
                cursor = conn.cursor()
                if param.isdigit():
                    cursor.execute("SELECT * FROM receipts WHERE id = ?;", (int(param),))
                else:
                    cursor.execute("SELECT * FROM receipts WHERE receipt_no = ?;", (param,))
                rcp = cursor.fetchone()
                if not rcp:
                    return self.send_error_json("Resit tidak ditemui.", 404)
                snapshot = json.loads(rcp["data_snapshot"])
                return self.send_json({"success": True, "receipt": dict(rcp), "snapshot": snapshot})

            # 11. Accounts Receivable (Aging Report)
            elif path == "/api/ar/aging":
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT i.id, i.invoice_no, i.service_type, i.grand_total, i.deposit_amount, i.paid_amount, i.balance_due,
                           i.status, i.created_at,
                           c.name as customer_name, c.phone as customer_phone,
                           v.reg_no as vehicle_reg, v.make as vehicle_make, v.model as vehicle_model,
                           CAST((julianday('now') - julianday(i.created_at)) AS INTEGER) as age_days
                    FROM invoices i
                    JOIN customers c ON i.customer_id = c.id
                    JOIN vehicles v ON i.vehicle_id = v.id
                    WHERE i.status IN ('APPROVED', 'PARTIALLY_PAID') AND i.balance_due > 0.001
                    ORDER BY age_days DESC;
                """)
                return self.send_json({"success": True, "ar": [dict(r) for r in cursor.fetchall()]})

            # 12. Cashier Closing
            elif path == "/api/cashier/closing":
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                cursor = conn.cursor()
                # Sum payments by method today
                cursor.execute("""
                    SELECT payment_method, SUM(amount) as total
                    FROM payments
                    WHERE date(created_at) = date('now')
                    GROUP BY payment_method;
                """)
                methods = {r["payment_method"]: float(r["total"]) for r in cursor.fetchall()}
                cash_collected = methods.get("CASH", 0.0)
                non_cash_collected = sum(v for k, v in methods.items() if k != "CASH")
                total_collected = cash_collected + non_cash_collected

                cursor.execute("SELECT * FROM cashier_closings WHERE closing_date = ? ORDER BY id DESC LIMIT 1;", (today,))
                closing_record = cursor.fetchone()

                return self.send_json({
                    "success": True,
                    "date": today,
                    "methods": methods,
                    "cash_collected": cash_collected,
                    "non_cash_collected": non_cash_collected,
                    "total_collected": total_collected,
                    "closing_record": dict(closing_record) if closing_record else None
                })

            # 13. Service Reminders
            elif path == "/api/reminders":
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT r.*, c.name as customer_name, c.phone as customer_phone, c.whatsapp as customer_whatsapp,
                           v.reg_no as vehicle_reg, v.make as vehicle_make, v.model as vehicle_model,
                           CAST((julianday(r.next_service_date) - julianday('now')) AS INTEGER) as days_left
                    FROM service_reminders r
                    JOIN customers c ON r.customer_id = c.id
                    JOIN vehicles v ON r.vehicle_id = v.id
                    WHERE r.status != 'COMPLETED'
                    ORDER BY r.next_service_date ASC;
                """)
                return self.send_json({"success": True, "reminders": [dict(r) for r in cursor.fetchall()]})

            # 14. Suppliers & Purchases
            elif path == "/api/suppliers":
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM suppliers WHERE status = 'ACTIVE' ORDER BY company ASC;")
                return self.send_json({"success": True, "suppliers": [dict(r) for r in cursor.fetchall()]})

            elif path == "/api/purchases":
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT p.*, s.company as supplier_name, u.name as creator_name
                    FROM purchases p
                    JOIN suppliers s ON p.supplier_id = s.id
                    LEFT JOIN users u ON p.created_by = u.id
                    ORDER BY p.id DESC;
                """)
                return self.send_json({"success": True, "purchases": [dict(r) for r in cursor.fetchall()]})

            # 15. Reports
            elif path.startswith("/api/reports/"):
                report_type = path.split("/api/reports/")[1]
                return self.handle_reports(conn, report_type, query)

            # 16. Audit Logs (Admin only)
            elif path == "/api/audit-logs":
                if user["role"] != "ADMIN":
                    return self.send_error_json("Akses tidak dibenarkan. Hanya ADMIN boleh melihat Log Audit.", 403)
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 150;")
                return self.send_json({"success": True, "logs": [dict(r) for r in cursor.fetchall()]})

            # 17. Users Management (Admin only)
            elif path == "/api/users":
                if user["role"] != "ADMIN":
                    return self.send_error_json("Akses tidak dibenarkan. Hanya ADMIN boleh menguruskan pengguna.", 403)
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, email, role, phone, is_active, last_login, created_at FROM users ORDER BY id ASC;")
                return self.send_json({"success": True, "users": [dict(r) for r in cursor.fetchall()]})

            # 18. Settings (Company Settings)
            elif path == "/api/settings":
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM company_settings WHERE id = 1;")
                return self.send_json({"success": True, "settings": dict(cursor.fetchone() or {})})

            elif path == "/api/settings/backup":
                if user["role"] != "ADMIN":
                    return self.send_error_json("Akses sandaran hanya dibenarkan untuk ADMIN.", 403)
                # Read sqlite file and send
                with open(DB_PATH, "rb") as f:
                    db_bytes = f.read()
                filename = f"GM_GEAR_ARAU_BACKUP_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f"attachment; filename=\"{filename}\"")
                self.send_header("Content-Length", str(len(db_bytes)))
                self.end_headers()
                self.wfile.write(db_bytes)
                return

            else:
                return self.send_error_json("Laluan API tidak ditemui.", 404)

        except Exception as e:
            return self.send_error_json(f"Ralat pelayan: {str(e)}", 500)
        finally:
            conn.close()

    # =========================================================================
    # POST REQUEST ROUTER
    # =========================================================================
    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        body = self.parse_json_body()
        ip = self.get_client_ip()

        # Public Login
        if path == "/api/auth/login":
            return self.handle_login(body, ip)

        # Protected endpoints
        user = self.get_auth_user()
        if not user:
            return self.send_error_json("Sila log masuk terlebih dahulu.", 401)

        conn = get_db_connection()
        try:
            # 1. Auth Logout
            if path == "/api/auth/logout":
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions WHERE token = ?;", (user["token"],))
                conn.commit()
                log_audit(user, "LOGOUT", "AUTH", user["email"], ip=ip)
                return self.send_json({"success": True, "message": "Log keluar berjaya."})

            # 2. Setup Password / Change Password
            elif path == "/api/auth/change-password":
                old_pass = body.get("old_password", "")
                new_pass = body.get("new_password", "")
                if not new_pass or len(new_pass) < 6:
                    return self.send_error_json("Kata laluan baharu mestilah sekurang-kurangnya 6 aksara.")

                cursor = conn.cursor()
                cursor.execute("SELECT password_hash, salt FROM users WHERE id = ?;", (user["id"],))
                u_row = cursor.fetchone()
                if not verify_password(old_pass, u_row["password_hash"], u_row["salt"]):
                    return self.send_error_json("Kata laluan semasa tidak tepat.")

                new_h, new_s = hash_password(new_pass)
                cursor.execute("UPDATE users SET password_hash = ?, salt = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (new_h, new_s, user["id"]))
                conn.commit()
                log_audit(user, "CHANGE_PASSWORD", "AUTH", str(user["id"]), ip=ip)
                return self.send_json({"success": True, "message": "Kata laluan berjaya dikemaskini."})

            # 3. Create Customer
            elif path == "/api/customers":
                name = body.get("name", "").strip()
                phone = body.get("phone", "").strip()
                if not name or not phone:
                    return self.send_error_json("Nama dan nombor telefon pelanggan adalah wajib.")

                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO customers (name, ic_company, phone, whatsapp, email, address, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (name, body.get("ic_company"), phone, body.get("whatsapp", phone), body.get("email"), body.get("address"), body.get("notes")))
                cust_id = cursor.lastrowid
                conn.commit()
                log_audit(user, "CREATE_CUSTOMER", "CUSTOMER", str(cust_id), new_val={"name": name, "phone": phone}, ip=ip)
                return self.send_json({"success": True, "customer_id": cust_id, "message": f"Pelanggan {name} berjaya ditambah."})

            # 4. Create Vehicle
            elif path == "/api/vehicles":
                customer_id = body.get("customer_id")
                reg_no = body.get("reg_no", "").strip().upper()
                v_type = body.get("vehicle_type", "CAR")
                make = body.get("make", "").strip()
                model = body.get("model", "").strip()

                if not customer_id or not reg_no or not make or not model:
                    return self.send_error_json("Sila lengkapkan ID Pelanggan, No. Pendaftaran Plat, Jenama, dan Model kenderaan.")

                cursor = conn.cursor()
                # Check duplicate plate
                cursor.execute("SELECT id FROM vehicles WHERE reg_no = ? AND status = 'ACTIVE';", (reg_no,))
                if cursor.fetchone():
                    return self.send_error_json(f"No. Pendaftaran {reg_no} telah pun wujud dalam sistem.")

                cursor.execute("""
                    INSERT INTO vehicles (customer_id, vehicle_type, reg_no, make, model, variant, year, engine, engine_cc, engine_no, chassis_vin, transmission, mileage, colour, colour_code, fuel_type, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (customer_id, v_type, reg_no, make, model, body.get("variant"), body.get("year"), body.get("engine"), body.get("engine_cc"), body.get("engine_no"), body.get("chassis_vin"), body.get("transmission"), body.get("mileage", 0), body.get("colour"), body.get("colour_code"), body.get("fuel_type", "Petrol"), body.get("notes")))
                v_id = cursor.lastrowid
                conn.commit()
                log_audit(user, "CREATE_VEHICLE", "VEHICLE", str(v_id), new_val={"reg_no": reg_no, "model": f"{make} {model}"}, ip=ip)
                return self.send_json({"success": True, "vehicle_id": v_id, "reg_no": reg_no, "message": f"Kenderaan {reg_no} berjaya didaftarkan."})

            # 5. Create Inventory Item
            elif path == "/api/inventory":
                sku = body.get("sku", "").strip().upper()
                name = body.get("name", "").strip()
                category = body.get("category", "General")
                selling_price = float(body.get("selling_price", 0.0))
                cost_price = float(body.get("cost_price", 0.0))
                stock_qty = float(body.get("stock_qty", 0.0))
                qr_id = body.get("qr_id", "").strip() or f"QR-{sku}"

                if not sku or not name:
                    return self.send_error_json("SKU dan Nama alat ganti adalah wajib.")

                cursor = conn.cursor()
                cursor.execute("SELECT id FROM inventory WHERE sku = ?;", (sku,))
                if cursor.fetchone():
                    return self.send_error_json(f"SKU {sku} telah wujud dalam pangkalan data.")

                cursor.execute("""
                    INSERT INTO inventory (sku, qr_id, name, category, brand, supplier_id, cost_price, selling_price, stock_qty, min_stock, reorder_qty, location, unit, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (sku, qr_id, name, category, body.get("brand"), body.get("supplier_id"), cost_price, selling_price, stock_qty, body.get("min_stock", 5), body.get("reorder_qty", 10), body.get("location"), body.get("unit", "PCS"), body.get("notes")))
                inv_id = cursor.lastrowid

                # Initial stock movement
                if stock_qty > 0:
                    cursor.execute("""
                        INSERT INTO stock_movements (inventory_id, qty, movement_type, before_qty, after_qty, user_id, reference_type, reference_id, reason)
                        VALUES (?, ?, 'IN', 0.0, ?, ?, 'MANUAL', 'NEW-ITEM', 'Kemasukan permulaan item baharu');
                    """, (inv_id, stock_qty, stock_qty, user["id"]))

                conn.commit()
                log_audit(user, "CREATE_INVENTORY", "INVENTORY", str(inv_id), new_val={"sku": sku, "name": name, "stock": stock_qty}, ip=ip)
                return self.send_json({"success": True, "inventory_id": inv_id, "qr_id": qr_id, "message": f"Item {name} ({sku}) berjaya ditambah."})

            # 6. Manual Stock Adjustment
            elif path == "/api/stock-movements":
                inv_id = body.get("inventory_id")
                qty = float(body.get("qty", 0.0))
                m_type = body.get("movement_type", "ADJUSTMENT")
                reason = body.get("reason", "").strip()

                if not inv_id or qty <= 0 or not reason:
                    return self.send_error_json("Sila lengkapkan ID item, kuantiti > 0, dan alasan pergerakan stok.")

                cursor = conn.cursor()
                cursor.execute("SELECT id, name, sku, stock_qty FROM inventory WHERE id = ?;", (inv_id,))
                item = cursor.fetchone()
                if not item:
                    return self.send_error_json("Item inventori tidak ditemui.", 404)

                before_qty = float(item["stock_qty"])
                if m_type == "IN":
                    after_qty = before_qty + qty
                elif m_type in ("OUT", "ADJUSTMENT"):
                    after_qty = max(0.0, before_qty - qty)
                else:
                    after_qty = before_qty + qty

                cursor.execute("UPDATE inventory SET stock_qty = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (after_qty, inv_id))
                cursor.execute("""
                    INSERT INTO stock_movements (inventory_id, qty, movement_type, before_qty, after_qty, user_id, reference_type, reference_id, reason)
                    VALUES (?, ?, ?, ?, ?, ?, 'MANUAL', 'STOCK-ADJ', ?);
                """, (inv_id, qty, m_type, before_qty, after_qty, user["id"], reason))
                conn.commit()
                log_audit(user, "STOCK_ADJUSTMENT", "INVENTORY", str(inv_id), prev_val={"stock": before_qty}, new_val={"stock": after_qty, "reason": reason}, ip=ip)
                return self.send_json({"success": True, "message": f"Stok {item['name']} dikemaskini dari {before_qty} ke {after_qty}."})

            # 7. Create Work Order / Job Card
            elif path == "/api/jobs":
                service_type = body.get("service_type", "AUTO_SERVICE")
                customer_id = body.get("customer_id")
                vehicle_id = body.get("vehicle_id")

                if not customer_id or not vehicle_id:
                    return self.send_error_json("Pelanggan dan kenderaan adalah wajib untuk membuka Kad Kerja.")

                job_no = business_logic.generate_reference_no("JOB-", "jobs", "job_no")
                items = body.get("items", [])

                parts_total = sum(float(i.get("amount", 0.0)) for i in items if i.get("item_type") == "PART")
                materials_total = sum(float(i.get("amount", 0.0)) for i in items if i.get("item_type") == "MATERIAL")
                labour_total = sum(float(i.get("amount", 0.0)) for i in items if i.get("item_type") == "LABOUR")
                discount = float(body.get("discount", 0.0))
                est_total = max(0.0, round(parts_total + materials_total + labour_total - discount, 2))

                # Body & Paint json serialization
                damaged_panels = json.dumps(body.get("damaged_panels", [])) if isinstance(body.get("damaged_panels"), list) else body.get("damaged_panels", "")
                damage_types = json.dumps(body.get("damage_types", [])) if isinstance(body.get("damage_types"), list) else body.get("damage_types", "")

                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO jobs (job_no, service_type, customer_id, vehicle_id, mileage, complaint, inspection, diagnosis, recommendation, technician_id, status, estimated_completion, parts_total, materials_total, labour_total, discount, estimated_total, notes, damage_description, repair_method, paint_colour, paint_code, damaged_panels, damage_types, paint_quantity, estimated_days, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (job_no, service_type, customer_id, vehicle_id, body.get("mileage", 0), body.get("complaint"), body.get("inspection"), body.get("diagnosis"), body.get("recommendation"), body.get("technician_id"), body.get("status", "IN_PROGRESS"), body.get("estimated_completion"), parts_total, materials_total, labour_total, discount, est_total, body.get("notes"), body.get("damage_description"), body.get("repair_method"), body.get("paint_colour"), body.get("paint_code"), damaged_panels, damage_types, float(body.get("paint_quantity", 0.0)), int(body.get("estimated_days", 1)), user["id"]))
                job_id = cursor.lastrowid

                # Insert items
                for itm in items:
                    cursor.execute("""
                        INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (job_id, itm.get("item_type", "PART"), itm.get("inventory_id"), itm.get("sku"), itm.get("name", "Item"), float(itm.get("qty", 1)), float(itm.get("unit_price", 0)), float(itm.get("amount", 0))))

                conn.commit()
                log_audit(user, "CREATE_JOB", "JOB", str(job_id), new_val={"job_no": job_no, "service_type": service_type, "total": est_total}, ip=ip)
                return self.send_json({"success": True, "job_id": job_id, "job_no": job_no, "message": f"Kad Kerja {job_no} berjaya dicipta."})

            # 8. Upload Job Photo (Body & Paint Before/During/After)
            elif path.startswith("/api/jobs/") and path.endswith("/images"):
                job_id = int(path.split("/api/jobs/")[1].split("/images")[0])
                stage = body.get("stage", "BEFORE")
                img_data = body.get("image_base64", "")
                caption = body.get("caption", "")

                if not img_data:
                    return self.send_error_json("Data gambar tidak disediakan.")

                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO job_images (job_id, stage, image_base64, caption)
                    VALUES (?, ?, ?, ?);
                """, (job_id, stage, img_data, caption))
                img_id = cursor.lastrowid
                conn.commit()
                log_audit(user, "UPLOAD_JOB_IMAGE", "JOB", str(job_id), new_val={"image_id": img_id, "stage": stage}, ip=ip)
                return self.send_json({"success": True, "image_id": img_id, "message": f"Gambar fasa {stage} berjaya dimuat naik."})

            # 9. Convert Job to Invoice
            elif path.startswith("/api/jobs/") and path.endswith("/convert-to-invoice"):
                job_id = int(path.split("/api/jobs/")[1].split("/convert-to-invoice")[0])
                res = business_logic.convert_job_to_invoice(job_id, user)
                if not res.get("success"):
                    return self.send_error_json(res.get("error", "Gagal menukar kad kerja ke invois."))
                return self.send_json(res)

            # 10. Create Quotation
            elif path == "/api/quotations":
                customer_id = body.get("customer_id")
                vehicle_id = body.get("vehicle_id")
                service_type = body.get("service_type", "AUTO_SERVICE")
                items = body.get("items", [])

                if not customer_id or not vehicle_id:
                    return self.send_error_json("Pelanggan dan kenderaan adalah wajib.")

                quote_no = business_logic.generate_reference_no("QUO-", "quotations", "quote_no")
                subtotal = sum(float(i.get("amount", 0.0)) for i in items)
                discount = float(body.get("discount", 0.0))
                tax = 0.0
                total = max(0.0, round(subtotal - discount + tax, 2))

                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO quotations (quote_no, customer_id, vehicle_id, service_type, subtotal, discount, tax, total, validity_date, status, notes, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?);
                """, (quote_no, customer_id, vehicle_id, service_type, subtotal, discount, tax, total, body.get("validity_date"), body.get("notes"), user["id"]))
                quote_id = cursor.lastrowid

                for itm in items:
                    cursor.execute("""
                        INSERT INTO quotation_lines (quotation_id, item_type, inventory_id, sku, description, qty, unit_price, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (quote_id, itm.get("item_type", "PART"), itm.get("inventory_id"), itm.get("sku"), itm.get("description", "Item"), float(itm.get("qty", 1)), float(itm.get("unit_price", 0)), float(itm.get("amount", 0))))

                conn.commit()
                log_audit(user, "CREATE_QUOTATION", "QUOTATION", str(quote_id), new_val={"quote_no": quote_no, "total": total}, ip=ip)
                return self.send_json({"success": True, "quotation_id": quote_id, "quote_no": quote_no, "message": f"Sebut harga {quote_no} berjaya dicipta."})

            # 11. Convert Quotation to Job
            elif path.startswith("/api/quotations/") and path.endswith("/convert-to-job"):
                quote_id = int(path.split("/api/quotations/")[1].split("/convert-to-job")[0])
                res = business_logic.convert_quotation_to_job(quote_id, user)
                if not res.get("success"):
                    return self.send_error_json(res.get("error", "Gagal menukar sebut harga."))
                return self.send_json(res)

            # 12. Create Direct Invoice
            elif path == "/api/invoices":
                customer_id = body.get("customer_id")
                vehicle_id = body.get("vehicle_id")
                service_type = body.get("service_type", "AUTO_SERVICE")
                items = body.get("items", [])

                if not customer_id or not vehicle_id:
                    return self.send_error_json("Pelanggan dan kenderaan adalah wajib.")

                invoice_no = business_logic.generate_reference_no("INV-", "invoices", "invoice_no")
                qr_token = business_logic.generate_qr_token()

                subtotal = sum(float(i.get("amount", 0.0)) for i in items)
                discount = float(body.get("discount", 0.0))
                tax = 0.0
                grand_total = max(0.0, round(subtotal - discount + tax, 2))

                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO invoices (invoice_no, customer_id, vehicle_id, service_type, subtotal, discount, tax, grand_total, deposit_amount, paid_amount, balance_due, status, qr_token, notes, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, ?, 'DRAFT', ?, ?, ?);
                """, (invoice_no, customer_id, vehicle_id, service_type, subtotal, discount, tax, grand_total, grand_total, qr_token, body.get("notes"), user["id"]))
                inv_id = cursor.lastrowid

                for itm in items:
                    cursor.execute("""
                        INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (inv_id, itm.get("item_type", "PART"), itm.get("inventory_id"), itm.get("sku"), itm.get("description", "Item"), float(itm.get("qty", 1)), float(itm.get("unit_price", 0)), float(itm.get("amount", 0))))

                conn.commit()
                log_audit(user, "CREATE_INVOICE", "INVOICE", str(inv_id), new_val={"invoice_no": invoice_no, "grand_total": grand_total}, ip=ip)
                return self.send_json({"success": True, "invoice_id": inv_id, "invoice_no": invoice_no, "qr_token": qr_token, "message": f"Invois {invoice_no} berjaya dicipta."})

            # 13. Approve Invoice (Atomic Stock Deduction Exactly Once)
            elif path.startswith("/api/invoices/") and path.endswith("/approve"):
                inv_id = int(path.split("/api/invoices/")[1].split("/approve")[0])
                res = business_logic.approve_invoice_transaction(inv_id, user)
                if not res.get("success"):
                    return self.send_error_json(res.get("error", "Gagal meluluskan invois."))
                return self.send_json(res)

            # 14. Cancel Invoice (Atomic Stock Reversal Exactly Once)
            elif path.startswith("/api/invoices/") and path.endswith("/cancel"):
                inv_id = int(path.split("/api/invoices/")[1].split("/cancel")[0])
                reason = body.get("reason", "").strip()
                res = business_logic.cancel_invoice_transaction(inv_id, user, reason)
                if not res.get("success"):
                    return self.send_error_json(res.get("error", "Gagal membatalkan invois."))
                return self.send_json(res)

            # 15. Record Payment / Deposit (Atomic receipt generation & balance reduction)
            elif path == "/api/payments":
                inv_id = body.get("invoice_id")
                amount = float(body.get("amount", 0.0))
                method = body.get("payment_method", "CASH")
                p_type = body.get("payment_type", "FINAL")
                ref_no = body.get("reference_no")
                notes = body.get("notes")

                if not inv_id or amount <= 0:
                    return self.send_error_json("Sila lengkapkan invois dan jumlah bayaran yang sah (> RM 0.00).")

                res = business_logic.record_payment_transaction(inv_id, amount, method, p_type, user, ref_no, notes)
                if not res.get("success"):
                    return self.send_error_json(res.get("error", "Gagal merekodkan pembayaran."))
                return self.send_json(res)

            # 16. Submit Cashier Closing
            elif path == "/api/cashier/closing":
                actual_cash = float(body.get("actual_cash", 0.0))
                notes = body.get("notes", "")
                today = datetime.datetime.now().strftime("%Y-%m-%d")

                cursor = conn.cursor()
                cursor.execute("""
                    SELECT payment_method, SUM(amount) as total
                    FROM payments
                    WHERE date(created_at) = date('now')
                    GROUP BY payment_method;
                """)
                methods = {r["payment_method"]: float(r["total"]) for r in cursor.fetchall()}
                cash_collected = methods.get("CASH", 0.0)
                non_cash_collected = sum(v for k, v in methods.items() if k != "CASH")
                total_collected = cash_collected + non_cash_collected
                opening_cash = float(body.get("opening_cash", 0.0))
                expected_cash = opening_cash + cash_collected
                diff = actual_cash - expected_cash

                cursor.execute("""
                    INSERT INTO cashier_closings (closing_date, user_id, opening_cash, cash_collected, non_cash_collected, total_collected, expected_cash, actual_cash, difference, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CLOSED', ?);
                """, (today, user["id"], opening_cash, cash_collected, non_cash_collected, total_collected, expected_cash, actual_cash, diff, notes))
                closing_id = cursor.lastrowid
                conn.commit()
                log_audit(user, "CASHIER_CLOSING", "FINANCE", str(closing_id), new_val={"actual": actual_cash, "expected": expected_cash, "diff": diff}, ip=ip)
                return self.send_json({"success": True, "message": "Penyata Penutupan Harian Kaunter berjaya disimpan.", "difference": diff})

            # 17. Update Company Settings (Admin only)
            elif path == "/api/settings":
                if user["role"] != "ADMIN":
                    return self.send_error_json("Akses ditolak. Hanya ADMIN boleh mengemaskini Tetapan Syarikat.", 403)

                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE company_settings
                    SET company_name = ?, trading_name = ?, reg_no = ?, phone = ?, email = ?,
                        address = ?, currency = ?, tax_enabled = ?, tax_rate = ?,
                        invoice_prefix = ?, job_prefix = ?, receipt_prefix = ?, quote_prefix = ?,
                        invoice_footer = ?, receipt_footer = ?, low_stock_threshold = ?,
                        logo_base64 = COALESCE(?, logo_base64),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1;
                """, (body.get("company_name", "GM GEAR ARAU"), body.get("trading_name"), body.get("reg_no"), body.get("phone"), body.get("email"), body.get("address"), body.get("currency", "RM"), int(body.get("tax_enabled", 0)), float(body.get("tax_rate", 6.0)), body.get("invoice_prefix", "INV-2026-"), body.get("job_prefix", "JOB-2026-"), body.get("receipt_prefix", "RCP-2026-"), body.get("quote_prefix", "QUO-2026-"), body.get("invoice_footer"), body.get("receipt_footer"), int(body.get("low_stock_threshold", 5)), body.get("logo_base64")))
                conn.commit()
                log_audit(user, "UPDATE_SETTINGS", "SETTINGS", "1", new_val={"company_name": body.get("company_name")}, ip=ip)
                return self.send_json({"success": True, "message": "Tetapan syarikat berjaya dikemaskini."})

            # 18. Purge Demo Data (Admin only)
            elif path == "/api/settings/purge-demo":
                if user["role"] != "ADMIN":
                    return self.send_error_json("Akses ditolak. Hanya ADMIN boleh memadamkan Data Demo.", 403)
                res = business_logic.purge_demo_data_transaction(user)
                if not res.get("success"):
                    return self.send_error_json(res.get("error", "Gagal memadam data demo."))
                return self.send_json(res)

            # 19. Create User (Admin only)
            elif path == "/api/users":
                if user["role"] != "ADMIN":
                    return self.send_error_json("Akses ditolak. Hanya ADMIN boleh mencipta pengguna.", 403)
                u_name = body.get("name", "").strip()
                u_email = body.get("email", "").strip().lower()
                u_pass = body.get("password", "").strip()
                u_role = body.get("role", "MECHANIC")

                if not u_name or not u_email or not u_pass:
                    return self.send_error_json("Nama, emel, dan kata laluan adalah wajib.")

                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE email = ?;", (u_email,))
                if cursor.fetchone():
                    return self.send_error_json(f"Pengguna dengan emel {u_email} telah sedia wujud.")

                p_hash, p_salt = hash_password(u_pass)
                cursor.execute("""
                    INSERT INTO users (name, email, password_hash, salt, role, phone)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (u_name, u_email, p_hash, p_salt, u_role, body.get("phone")))
                new_uid = cursor.lastrowid
                conn.commit()
                log_audit(user, "CREATE_USER", "USERS", str(new_uid), new_val={"name": u_name, "role": u_role, "email": u_email}, ip=ip)
                return self.send_json({"success": True, "user_id": new_uid, "message": f"Pengguna {u_name} ({u_role}) berjaya dicipta."})

            # 20. Update Job Status / Progress
            elif path.startswith("/api/jobs/") and path.endswith("/update-status"):
                job_id = int(path.split("/api/jobs/")[1].split("/update-status")[0])
                new_status = body.get("status", "")
                if not new_status:
                    return self.send_error_json("Status baharu diperlukan.")

                cursor = conn.cursor()
                cursor.execute("UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (new_status, job_id))
                conn.commit()
                log_audit(user, "UPDATE_JOB_STATUS", "JOB", str(job_id), new_val={"status": new_status}, ip=ip)
                return self.send_json({"success": True, "message": f"Status Kad Kerja dikemaskini ke {new_status}."})

            else:
                return self.send_error_json("Laluan API POST tidak ditemui.", 404)

        except Exception as e:
            return self.send_error_json(f"Ralat pelayan: {str(e)}", 500)
        finally:
            conn.close()

    # =========================================================================
    # PUT & DELETE HANDLERS
    # =========================================================================
    def do_PUT(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        body = self.parse_json_body()
        user = self.get_auth_user()
        if not user:
            return self.send_error_json("Sila log masuk.", 401)

        conn = get_db_connection()
        try:
            if path.startswith("/api/customers/"):
                c_id = int(path.split("/api/customers/")[1])
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE customers
                    SET name = ?, ic_company = ?, phone = ?, whatsapp = ?, email = ?, address = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (body.get("name"), body.get("ic_company"), body.get("phone"), body.get("whatsapp"), body.get("email"), body.get("address"), body.get("notes"), c_id))
                conn.commit()
                log_audit(user, "UPDATE_CUSTOMER", "CUSTOMER", str(c_id), new_val=body, ip=self.get_client_ip())
                return self.send_json({"success": True, "message": "Maklumat pelanggan dikemaskini."})

            elif path.startswith("/api/inventory/"):
                inv_id = int(path.split("/api/inventory/")[1])
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE inventory
                    SET name = ?, category = ?, brand = ?, cost_price = ?, selling_price = ?, min_stock = ?, reorder_qty = ?, location = ?, unit = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (body.get("name"), body.get("category"), body.get("brand"), float(body.get("cost_price", 0)), float(body.get("selling_price", 0)), float(body.get("min_stock", 5)), float(body.get("reorder_qty", 10)), body.get("location"), body.get("unit", "PCS"), body.get("notes"), inv_id))
                conn.commit()
                log_audit(user, "UPDATE_INVENTORY", "INVENTORY", str(inv_id), new_val=body, ip=self.get_client_ip())
                return self.send_json({"success": True, "message": "Maklumat alat ganti dikemaskini."})

            else:
                return self.send_error_json("Laluan API PUT tidak ditemui.", 404)
        finally:
            conn.close()

    def do_DELETE(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        user = self.get_auth_user()
        if not user:
            return self.send_error_json("Sila log masuk.", 401)

        # Soft delete / Archive
        conn = get_db_connection()
        try:
            if path.startswith("/api/customers/"):
                c_id = int(path.split("/api/customers/")[1])
                cursor = conn.cursor()
                cursor.execute("UPDATE customers SET status = 'ARCHIVED', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (c_id,))
                conn.commit()
                log_audit(user, "ARCHIVE_CUSTOMER", "CUSTOMER", str(c_id), ip=self.get_client_ip())
                return self.send_json({"success": True, "message": "Rekod pelanggan telah diarkibkan."})

            elif path.startswith("/api/vehicles/"):
                v_id = int(path.split("/api/vehicles/")[1])
                cursor = conn.cursor()
                cursor.execute("UPDATE vehicles SET status = 'ARCHIVED', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (v_id,))
                conn.commit()
                log_audit(user, "ARCHIVE_VEHICLE", "VEHICLE", str(v_id), ip=self.get_client_ip())
                return self.send_json({"success": True, "message": "Rekod kenderaan telah diarkibkan."})

            elif path.startswith("/api/inventory/"):
                inv_id = int(path.split("/api/inventory/")[1])
                cursor = conn.cursor()
                cursor.execute("UPDATE inventory SET status = 'ARCHIVED', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (inv_id,))
                conn.commit()
                log_audit(user, "ARCHIVE_INVENTORY", "INVENTORY", str(inv_id), ip=self.get_client_ip())
                return self.send_json({"success": True, "message": "Item inventori telah diarkibkan."})

            else:
                return self.send_error_json("Laluan API DELETE tidak ditemui.", 404)
        finally:
            conn.close()

    # =========================================================================
    # HELPER CONTROLLERS
    # =========================================================================
    def serve_file(self, full_path: str, content_type: str):
        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error_json("Fail tidak ditemui.", 404)

    def handle_login(self, body: Dict[str, Any], ip: str):
        email = body.get("email", "").strip().lower()
        password = body.get("password", "").strip()

        if not email or not password:
            return self.send_error_json("Sila masukkan emel dan kata laluan.")

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ? AND is_active = 1;", (email,))
            user = cursor.fetchone()
            if not user or not verify_password(password, user["password_hash"], user["salt"]):
                log_audit(None, "LOGIN_FAILED", "AUTH", email, new_val={"email": email, "reason": "Kredensial tidak sah"}, ip=ip)
                return self.send_error_json("Emel atau kata laluan tidak tepat.", 401)

            # Create session token
            token = secrets.token_hex(24)
            expires = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO sessions (token, user_id, role, expires_at)
                VALUES (?, ?, ?, ?);
            """, (token, user["id"], user["role"], expires))
            cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?;", (user["id"],))
            conn.commit()

            cursor.execute("SELECT * FROM company_settings WHERE id = 1;")
            company = dict(cursor.fetchone() or {})

            user_dict = {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "phone": user["phone"]
            }
            log_audit(user_dict, "LOGIN_SUCCESS", "AUTH", email, ip=ip)

            return self.send_json({
                "success": True,
                "message": f"Selamat datang ke TRIG PROFESSIONAL, {user['name']}!",
                "token": token,
                "user": user_dict,
                "company": company
            })
        finally:
            conn.close()

    def handle_get_company_info(self):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT company_name, trading_name, reg_no, phone, email, address, currency, logo_base64 FROM company_settings WHERE id = 1;")
            row = cursor.fetchone()
            return self.send_json({"success": True, "company": dict(row or {})})
        finally:
            conn.close()

    def handle_dashboard_stats(self, conn: sqlite3.Connection, query: Dict[str, List[str]]):
        cursor = conn.cursor()
        service_type = query.get("service_type", [""])[0].strip()

        if service_type in ("AUTO_SERVICE", "BODY_PAINT", "MOTORCYCLE"):
            # Filtered by active service category
            cursor.execute("""
                SELECT COALESCE(SUM(p.amount), 0.0)
                FROM payments p
                JOIN invoices i ON p.invoice_id = i.id
                WHERE i.service_type = ? AND date(p.created_at) = date('now');
            """, (service_type,))
            today_collection = float(cursor.fetchone()[0])

            cursor.execute("""
                SELECT COALESCE(SUM(grand_total), 0.0)
                FROM invoices
                WHERE service_type = ? AND date(created_at) = date('now') AND status != 'CANCELLED';
            """, (service_type,))
            today_revenue = float(cursor.fetchone()[0])

            cursor.execute("""
                SELECT COALESCE(SUM(balance_due), 0.0)
                FROM invoices
                WHERE service_type = ? AND status IN ('APPROVED', 'PARTIALLY_PAID');
            """, (service_type,))
            outstanding_balance = float(cursor.fetchone()[0])

            cursor.execute("SELECT COUNT(*) FROM jobs WHERE service_type = ? AND date(created_at) = date('now');", (service_type,))
            jobs_today = int(cursor.fetchone()[0])

            cursor.execute("""
                SELECT COUNT(*) FROM jobs
                WHERE service_type = ? AND status IN ('IN_PROGRESS', 'PAINTING', 'PREPARATION', 'PRIMER', 'BODY_REPAIR');
            """, (service_type,))
            jobs_in_progress = int(cursor.fetchone()[0])

            cursor.execute("""
                SELECT COUNT(*) FROM jobs
                WHERE service_type = ? AND status IN ('COMPLETED', 'QC', 'READY');
            """, (service_type,))
            vehicles_ready = int(cursor.fetchone()[0])
        else:
            # Overall revenue and collections today
            cursor.execute("SELECT COALESCE(SUM(amount), 0.0) FROM payments WHERE date(created_at) = date('now');")
            today_collection = float(cursor.fetchone()[0])

            cursor.execute("SELECT COALESCE(SUM(grand_total), 0.0) FROM invoices WHERE date(created_at) = date('now') AND status != 'CANCELLED';")
            today_revenue = float(cursor.fetchone()[0])

            cursor.execute("SELECT COALESCE(SUM(balance_due), 0.0) FROM invoices WHERE status IN ('APPROVED', 'PARTIALLY_PAID');")
            outstanding_balance = float(cursor.fetchone()[0])

            cursor.execute("SELECT COUNT(*) FROM jobs WHERE date(created_at) = date('now');")
            jobs_today = int(cursor.fetchone()[0])

            cursor.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('IN_PROGRESS', 'PAINTING', 'PREPARATION', 'PRIMER', 'BODY_REPAIR');")
            jobs_in_progress = int(cursor.fetchone()[0])

            cursor.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('COMPLETED', 'QC', 'READY');")
            vehicles_ready = int(cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM inventory WHERE stock_qty <= min_stock AND status = 'ACTIVE';")
        low_stock_count = int(cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM customers WHERE status = 'ACTIVE';")
        total_customers = int(cursor.fetchone()[0])

        # By Service Category stats
        categories = ["AUTO_SERVICE", "BODY_PAINT", "MOTORCYCLE"]
        category_stats = {}
        for cat in categories:
            cursor.execute("SELECT COALESCE(SUM(grand_total), 0.0), COUNT(*) FROM invoices WHERE service_type = ? AND status != 'CANCELLED';", (cat,))
            r_inv = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE service_type = ?;", (cat,))
            cnt_job = cursor.fetchone()[0]
            category_stats[cat] = {
                "revenue": float(r_inv[0]),
                "invoices_count": int(r_inv[1]),
                "jobs_count": int(cnt_job)
            }

        return self.send_json({
            "success": True,
            "stats": {
                "today_revenue": today_revenue,
                "today_collection": today_collection,
                "outstanding_balance": outstanding_balance,
                "jobs_today": jobs_today,
                "jobs_in_progress": jobs_in_progress,
                "vehicles_ready": vehicles_ready,
                "low_stock_count": low_stock_count,
                "total_customers": total_customers,
                "category_stats": category_stats
            }
        })

    def handle_dashboard_charts(self, conn: sqlite3.Connection, query: Dict[str, List[str]]):
        cursor = conn.cursor()

        # 1. Revenue last 7 days
        cursor.execute("""
            SELECT date(created_at) as day, SUM(grand_total) as daily_total
            FROM invoices
            WHERE status != 'CANCELLED' AND date(created_at) >= date('now', '-6 days')
            GROUP BY date(created_at)
            ORDER BY day ASC;
        """)
        revenue_trend = [dict(r) for r in cursor.fetchall()]

        # 2. Payment methods distribution
        cursor.execute("""
            SELECT payment_method, SUM(amount) as total
            FROM payments
            GROUP BY payment_method;
        """)
        payment_methods = [dict(r) for r in cursor.fetchall()]

        # 3. Job status counts
        cursor.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status;")
        job_statuses = [dict(r) for r in cursor.fetchall()]

        # 4. Top selling parts
        cursor.execute("""
            SELECT sku, description, SUM(qty) as total_qty, SUM(amount) as total_amount
            FROM invoice_lines
            WHERE item_type = 'PART'
            GROUP BY sku, description
            ORDER BY total_qty DESC LIMIT 5;
        """)
        top_parts = [dict(r) for r in cursor.fetchall()]

        # 5. Service category distribution
        cursor.execute("""
            SELECT service_type, COUNT(*) as job_count, SUM(estimated_total) as total_value
            FROM jobs
            GROUP BY service_type;
        """)
        category_perf = [dict(r) for r in cursor.fetchall()]

        return self.send_json({
            "success": True,
            "charts": {
                "revenue_trend": revenue_trend,
                "payment_methods": payment_methods,
                "job_statuses": job_statuses,
                "top_parts": top_parts,
                "category_performance": category_perf
            }
        })

    def handle_global_search(self, conn: sqlite3.Connection, q: str):
        if not q or len(q) < 2:
            return self.send_json({"success": True, "results": []})

        cursor = conn.cursor()
        param = f"%{q}%"

        # Customers
        cursor.execute("SELECT id, name, phone, email, 'CUSTOMER' as entity_type FROM customers WHERE name LIKE ? OR phone LIKE ? LIMIT 5;", (param, param))
        custs = [dict(r) for r in cursor.fetchall()]

        # Vehicles
        cursor.execute("SELECT id, reg_no, make, model, chassis_vin, 'VEHICLE' as entity_type FROM vehicles WHERE reg_no LIKE ? OR chassis_vin LIKE ? LIMIT 5;", (param, param))
        vehs = [dict(r) for r in cursor.fetchall()]

        # Jobs
        cursor.execute("SELECT id, job_no, service_type, status, 'JOB' as entity_type FROM jobs WHERE job_no LIKE ? LIMIT 5;", (param,))
        jobs = [dict(r) for r in cursor.fetchall()]

        # Invoices
        cursor.execute("SELECT id, invoice_no, service_type, grand_total, status, 'INVOICE' as entity_type FROM invoices WHERE invoice_no LIKE ? LIMIT 5;", (param,))
        invs = [dict(r) for r in cursor.fetchall()]

        # Receipts
        cursor.execute("SELECT id, receipt_no, receipt_type, 'RECEIPT' as entity_type FROM receipts WHERE receipt_no LIKE ? LIMIT 5;", (param,))
        rcps = [dict(r) for r in cursor.fetchall()]

        # Inventory
        cursor.execute("SELECT id, sku, name, selling_price, stock_qty, 'INVENTORY' as entity_type FROM inventory WHERE sku LIKE ? OR name LIKE ? OR qr_id LIKE ? LIMIT 5;", (param, param, param))
        inv_items = [dict(r) for r in cursor.fetchall()]

        results = {
            "customers": custs,
            "vehicles": vehs,
            "jobs": jobs,
            "invoices": invs,
            "receipts": rcps,
            "inventory": inv_items
        }
        return self.send_json({"success": True, "results": results})

    def handle_customer_detail(self, conn: sqlite3.Connection, cust_id: int):
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE id = ?;", (cust_id,))
        cust = cursor.fetchone()
        if not cust:
            return self.send_error_json("Pelanggan tidak ditemui.", 404)

        cursor.execute("SELECT * FROM vehicles WHERE customer_id = ? AND status = 'ACTIVE';", (cust_id,))
        vehicles = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM jobs WHERE customer_id = ? ORDER BY id DESC LIMIT 20;", (cust_id,))
        jobs = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM invoices WHERE customer_id = ? ORDER BY id DESC LIMIT 20;", (cust_id,))
        invoices = [dict(r) for r in cursor.fetchall()]

        res = dict(cust)
        res["vehicles"] = vehicles
        res["jobs"] = jobs
        res["invoices"] = invoices
        return self.send_json({"success": True, "customer": res})

    def handle_reports(self, conn: sqlite3.Connection, report_type: str, query: Dict[str, List[str]]):
        service_type = query.get("service_type", [""])[0]
        cursor = conn.cursor()

        svc_filter = ""
        svc_params = []
        if service_type and service_type != "ALL":
            svc_filter = "AND service_type = ?"
            svc_params.append(service_type)

        if report_type == "sales":
            cursor.execute(f"""
                SELECT invoice_no, service_type, grand_total, deposit_amount, paid_amount, balance_due, status, created_at
                FROM invoices
                WHERE status != 'CANCELLED' {svc_filter}
                ORDER BY id DESC LIMIT 150;
            """, svc_params)
            rows = [dict(r) for r in cursor.fetchall()]
            return self.send_json({"success": True, "sales_report": rows})

        elif report_type == "body-paint":
            # Specialized Body & Paint Report
            cursor.execute("""
                SELECT COUNT(*) as total_jobs,
                       COALESCE(SUM(materials_total), 0.0) as total_materials_cost,
                       COALESCE(SUM(labour_total), 0.0) as total_labour,
                       COALESCE(SUM(estimated_total), 0.0) as total_revenue,
                       COALESCE(AVG(estimated_days), 0.0) as avg_duration_days
                FROM jobs
                WHERE service_type = 'BODY_PAINT';
            """)
            summary = dict(cursor.fetchone() or {})

            cursor.execute("""
                SELECT j.job_no, j.paint_colour, j.paint_code, j.damaged_panels, j.damage_types,
                       j.status, j.materials_total, j.labour_total, j.estimated_total,
                       v.reg_no, v.make, v.model
                FROM jobs j
                JOIN vehicles v ON j.vehicle_id = v.id
                WHERE j.service_type = 'BODY_PAINT'
                ORDER BY j.id DESC LIMIT 50;
            """)
            jobs = [dict(r) for r in cursor.fetchall()]

            return self.send_json({"success": True, "summary": summary, "jobs": jobs})

        elif report_type == "mechanic-workload":
            cursor.execute("""
                SELECT u.id, u.name, u.role,
                       COUNT(j.id) as total_assigned,
                       SUM(CASE WHEN j.status IN ('COMPLETED', 'QC', 'READY') THEN 1 ELSE 0 END) as completed_jobs,
                       SUM(CASE WHEN j.status IN ('IN_PROGRESS', 'PAINTING', 'PREPARATION', 'PRIMER', 'BODY_REPAIR') THEN 1 ELSE 0 END) as ongoing_jobs
                FROM users u
                LEFT JOIN jobs j ON u.id = j.technician_id
                WHERE u.role = 'MECHANIC' OR u.id IN (SELECT DISTINCT technician_id FROM jobs WHERE technician_id IS NOT NULL)
                GROUP BY u.id, u.name, u.role;
            """)
            return self.send_json({"success": True, "mechanics": [dict(r) for r in cursor.fetchall()]})

        return self.send_error_json("Jenis laporan tidak dikenali.", 404)

def run_server(port=PORT):
    # Ensure static dir exists
    os.makedirs(STATIC_DIR, exist_ok=True)
    server_address = ("0.0.0.0", port)
    httpd = ThreadedHTTPServer(server_address, TrigPOSHandler)
    print(f"============================================================")
    print(f"TRIG PROFESSIONAL - AUTO WORKSHOP MANAGEMENT & POS SYSTEM")
    print(f"BENGKEL: GM GEAR ARAU")
    print(f"Server berjalan di: http://localhost:{port}")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nMematikan pelayan TRIG POS...")
        httpd.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(port)
