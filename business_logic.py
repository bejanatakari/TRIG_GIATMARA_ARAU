"""
TRIG PROFESSIONAL - AUTO WORKSHOP MANAGEMENT & POS SYSTEM
GM GEAR ARAU
Business Logic Module: Atomic Transactions, Sequential Numbering, Stock Ledger & Audit Safety
"""

import sqlite3
import datetime
import json
import secrets
from typing import Optional, Dict, Any, List, Tuple
from database import get_db_connection, log_audit

def generate_reference_no(prefix: str, table_name: str, column_name: str) -> str:
    """Generate collision-free sequential identifier (e.g. JOB-2026-000001)."""
    conn = get_db_connection()
    try:
        current_year = datetime.datetime.now().strftime("%Y")
        pattern = f"{prefix}{current_year}-%"
        cursor = conn.cursor()
        cursor.execute(f"SELECT {column_name} FROM {table_name} WHERE {column_name} LIKE ? ORDER BY id DESC LIMIT 1;", (pattern,))
        row = cursor.fetchone()
        if row and row[0]:
            last_no = row[0]
            try:
                seq_part = int(last_no.split("-")[-1])
                new_seq = seq_part + 1
            except Exception:
                new_seq = 1
        else:
            new_seq = 1
        return f"{prefix}{current_year}-{new_seq:06d}"
    finally:
        conn.close()

def generate_qr_token() -> str:
    """Generate secure unique non-sensitive URL token for invoice scanning."""
    return f"INV-TOKEN-{secrets.token_hex(12).upper()}"

def approve_invoice_transaction(invoice_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Approve Invoice:
    - Atomically deducts inventory stock EXACTLY ONCE.
    - Writes immutable entries to Stock Ledger (stock_movements).
    - Idempotent: If already approved, does not deduct again.
    - Writes Audit Log.
    """
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM invoices WHERE id = ?;", (invoice_id,))
        invoice = cursor.fetchone()
        if not invoice:
            conn.rollback()
            return {"success": False, "error": "Invois tidak ditemui."}

        # Idempotent check: If already approved, do not deduct stock again
        if invoice["approved_at"] is not None:
            conn.rollback()
            return {"success": True, "already_approved": True, "status": invoice["status"], "message": "Invois telah pun diluluskan sebelum ini. Stok tidak ditolak semula."}

        if invoice["status"] == "CANCELLED":
            conn.rollback()
            return {"success": False, "error": "Invois yang telah dibatalkan tidak boleh diluluskan."}

        # Fetch part lines to deduct stock
        cursor.execute("""
            SELECT id, inventory_id, sku, description, qty, unit_price
            FROM invoice_lines
            WHERE invoice_id = ? AND item_type = 'PART' AND inventory_id IS NOT NULL;
        """, (invoice_id,))
        part_lines = cursor.fetchall()

        # Check stock and deduct
        for line in part_lines:
            inv_id = line["inventory_id"]
            qty = float(line["qty"])
            cursor.execute("SELECT id, name, sku, stock_qty FROM inventory WHERE id = ?;", (inv_id,))
            inv_item = cursor.fetchone()
            if inv_item:
                before_qty = float(inv_item["stock_qty"])
                after_qty = before_qty - qty
                # Update stock quantity
                cursor.execute("UPDATE inventory SET stock_qty = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (after_qty, inv_id))
                # Insert into Stock Ledger
                cursor.execute("""
                    INSERT INTO stock_movements (inventory_id, qty, movement_type, before_qty, after_qty, user_id, reference_type, reference_id, reason)
                    VALUES (?, ?, 'OUT', ?, ?, ?, 'INVOICE', ?, ?);
                """, (inv_id, qty, before_qty, after_qty, user.get("id"), invoice["invoice_no"], f"Kelulusan Invois {invoice['invoice_no']}"))

        # Update invoice status
        new_status = "PAID" if float(invoice["balance_due"]) <= 0.001 else ("PARTIALLY_PAID" if float(invoice["paid_amount"]) > 0 else "APPROVED")
        cursor.execute("""
            UPDATE invoices
            SET status = ?, approved_at = CURRENT_TIMESTAMP, approved_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (new_status, user.get("id"), invoice_id))

        # Log audit
        cursor.execute("""
            INSERT INTO audit_logs (user_id, user_name, role, action, module, record_id, prev_value, new_value)
            VALUES (?, ?, ?, 'INVOICE_APPROVED', 'INVOICE', ?, ?, ?);
        """, (user.get("id"), user.get("name"), user.get("role"), str(invoice_id),
              json.dumps({"status": invoice["status"]}),
              json.dumps({"status": "APPROVED", "parts_deducted": len(part_lines)})))

        conn.commit()
        return {"success": True, "message": f"Invois {invoice['invoice_no']} berjaya diluluskan. Stok telah ditolak secara rasmi.", "parts_deducted": len(part_lines)}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Ralat transaksi pangkalan data: {str(e)}"}
    finally:
        conn.close()

def cancel_invoice_transaction(invoice_id: int, user: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """
    Cancel Invoice:
    - If previously APPROVED, reverses the stock deduction EXACTLY ONCE.
    - Records RETURN in Stock Ledger.
    - Records cancellation audit log.
    - Preserves invoice record without hard-deleting.
    """
    if not reason or not reason.strip():
        return {"success": False, "error": "Sila nyatakan sebab pembatalan invois."}

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM invoices WHERE id = ?;", (invoice_id,))
        invoice = cursor.fetchone()
        if not invoice:
            conn.rollback()
            return {"success": False, "error": "Invois tidak ditemui."}

        if invoice["status"] == "CANCELLED":
            conn.rollback()
            return {"success": False, "error": "Invois ini telah pun dibatalkan sebelum ini."}

        prev_status = invoice["status"]
        reversal_count = 0

        # If stock was deducted (indicated by approved_at having been set), return stock
        if invoice["approved_at"] is not None:
            cursor.execute("""
                SELECT id, inventory_id, sku, description, qty
                FROM invoice_lines
                WHERE invoice_id = ? AND item_type = 'PART' AND inventory_id IS NOT NULL;
            """, (invoice_id,))
            part_lines = cursor.fetchall()

            for line in part_lines:
                inv_id = line["inventory_id"]
                qty = float(line["qty"])
                cursor.execute("SELECT id, name, sku, stock_qty FROM inventory WHERE id = ?;", (inv_id,))
                inv_item = cursor.fetchone()
                if inv_item:
                    before_qty = float(inv_item["stock_qty"])
                    after_qty = before_qty + qty
                    cursor.execute("UPDATE inventory SET stock_qty = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (after_qty, inv_id))
                    cursor.execute("""
                        INSERT INTO stock_movements (inventory_id, qty, movement_type, before_qty, after_qty, user_id, reference_type, reference_id, reason)
                        VALUES (?, ?, 'RETURN', ?, ?, ?, 'CANCEL_INVOICE', ?, ?);
                    """, (inv_id, qty, before_qty, after_qty, user.get("id"), invoice["invoice_no"], f"Pembatalan Invois {invoice['invoice_no']}: {reason}"))
                    reversal_count += 1

        # Update status to CANCELLED
        cursor.execute("""
            UPDATE invoices
            SET status = 'CANCELLED', cancelled_at = CURRENT_TIMESTAMP, cancelled_by = ?, cancel_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (user.get("id"), reason, invoice_id))

        # Log audit
        cursor.execute("""
            INSERT INTO audit_logs (user_id, user_name, role, action, module, record_id, prev_value, new_value)
            VALUES (?, ?, ?, 'INVOICE_CANCELLED', 'INVOICE', ?, ?, ?);
        """, (user.get("id"), user.get("name"), user.get("role"), str(invoice_id),
              json.dumps({"status": prev_status}),
              json.dumps({"status": "CANCELLED", "reason": reason, "stock_reversed": reversal_count})))

        conn.commit()
        return {"success": True, "message": f"Invois {invoice['invoice_no']} berjaya dibatalkan. {reversal_count} item stok dipulangkan semula.", "reversals": reversal_count}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Ralat pembatalan invois: {str(e)}"}
    finally:
        conn.close()

def record_payment_transaction(invoice_id: int, amount: float, payment_method: str, payment_type: str, user: Dict[str, Any], reference_no: Optional[str] = None, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Atomic payment record:
    - Validates balance due.
    - Creates payment record with sequential receipt number RCP-2026-XXXXXX.
    - Generates immutable snapshot for thermal/A4 receipt printing.
    - Updates invoice paid amount and balance due.
    - Sets status to PAID if balance reaches 0.
    """
    if amount <= 0:
        return {"success": False, "error": "Jumlah bayaran mestilah melebihi RM 0.00."}

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT i.*, c.name as customer_name, c.phone as customer_phone,
                   v.reg_no as vehicle_reg, v.make as vehicle_make, v.model as vehicle_model
            FROM invoices i
            JOIN customers c ON i.customer_id = c.id
            JOIN vehicles v ON i.vehicle_id = v.id
            WHERE i.id = ?;
        """, (invoice_id,))
        invoice = cursor.fetchone()
        if not invoice:
            conn.rollback()
            return {"success": False, "error": "Invois tidak ditemui."}

        if invoice["status"] == "CANCELLED":
            conn.rollback()
            return {"success": False, "error": "Bayaran tidak boleh dibuat pada invois yang telah dibatalkan."}

        grand_total = float(invoice["grand_total"])
        current_paid = float(invoice["paid_amount"])
        current_balance = float(invoice["balance_due"])

        if current_balance <= 0.001 and invoice["status"] == "PAID":
            conn.rollback()
            return {"success": False, "error": "Invois ini telah pun dibayar penuh."}

        # Prevent overpayment unless minimal rounding tolerance
        if amount > (current_balance + 0.01):
            conn.rollback()
            return {"success": False, "error": f"Jumlah bayaran (RM {amount:.2f}) melebihi baki tertunggak (RM {current_balance:.2f})."}

        # Generate receipt number
        current_year = datetime.datetime.now().strftime("%Y")
        cursor.execute("SELECT receipt_no FROM payments WHERE receipt_no LIKE ? ORDER BY id DESC LIMIT 1;", (f"RCP-{current_year}-%",))
        last_row = cursor.fetchone()
        if last_row and last_row[0]:
            try:
                seq = int(last_row[0].split("-")[-1]) + 1
            except Exception:
                seq = 1
        else:
            seq = 1
        receipt_no = f"RCP-{current_year}-{seq:06d}"

        # Insert payment
        cursor.execute("""
            INSERT INTO payments (receipt_no, invoice_id, amount, payment_method, payment_type, reference_no, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (receipt_no, invoice_id, amount, payment_method, payment_type, reference_no, notes, user.get("id")))
        payment_id = cursor.lastrowid

        new_paid = current_paid + amount
        new_balance = max(0.0, round(grand_total - new_paid, 2))
        if new_balance <= 0.001:
            new_status = "PAID"
        elif invoice["approved_at"] is not None:
            new_status = "PARTIALLY_PAID"
        else:
            new_status = "DRAFT"

        # Update deposit if deposit payment
        deposit_clause = ""
        deposit_params = []
        if payment_type == "DEPOSIT":
            new_deposit = float(invoice["deposit_amount"]) + amount
            deposit_clause = ", deposit_amount = ?"
            deposit_params.append(new_deposit)

        update_query = f"""
            UPDATE invoices
            SET paid_amount = ?, balance_due = ?, status = ?, updated_at = CURRENT_TIMESTAMP{deposit_clause}
            WHERE id = ?;
        """
        cursor.execute(update_query, [new_paid, new_balance, new_status] + deposit_params + [invoice_id])

        # Fetch lines for receipt snapshot
        cursor.execute("SELECT sku, description, qty, unit_price, amount FROM invoice_lines WHERE invoice_id = ?;", (invoice_id,))
        lines = [dict(r) for r in cursor.fetchall()]

        # Create immutable receipt snapshot
        snapshot = {
            "receipt_no": receipt_no,
            "invoice_no": invoice["invoice_no"],
            "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "customer_name": invoice["customer_name"],
            "customer_phone": invoice["customer_phone"],
            "vehicle_reg": invoice["vehicle_reg"],
            "vehicle_model": f"{invoice['vehicle_make']} {invoice['vehicle_model']}",
            "service_type": invoice["service_type"],
            "grand_total": grand_total,
            "previous_paid": current_paid,
            "payment_amount": amount,
            "total_paid": new_paid,
            "balance_due": new_balance,
            "payment_method": payment_method,
            "payment_type": payment_type,
            "cashier_name": user.get("name", "Juruwang"),
            "items": lines
        }

        cursor.execute("""
            INSERT INTO receipts (receipt_no, payment_id, invoice_id, receipt_type, data_snapshot)
            VALUES (?, ?, ?, ?, ?);
        """, (receipt_no, payment_id, invoice_id, payment_type, json.dumps(snapshot, ensure_ascii=False)))

        # Log audit
        cursor.execute("""
            INSERT INTO audit_logs (user_id, user_name, role, action, module, record_id, prev_value, new_value)
            VALUES (?, ?, ?, 'PAYMENT_RECEIVED', 'PAYMENT', ?, ?, ?);
        """, (user.get("id"), user.get("name"), user.get("role"), receipt_no,
              json.dumps({"balance_due": current_balance}),
              json.dumps({"amount": amount, "method": payment_method, "new_balance": new_balance, "status": new_status})))

        conn.commit()
        return {
            "success": True,
            "message": f"Bayaran RM {amount:.2f} berjaya direkodkan. Resit: {receipt_no}",
            "receipt_no": receipt_no,
            "payment_id": payment_id,
            "balance_due": new_balance,
            "status": new_status,
            "snapshot": snapshot
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Ralat bayaran: {str(e)}"}
    finally:
        conn.close()

def convert_job_to_invoice(job_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an existing Work Order / Job Card into a draft/approved Invoice."""
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,))
        job = cursor.fetchone()
        if not job:
            conn.rollback()
            return {"success": False, "error": "Kad Kerja tidak ditemui."}

        # Check if invoice already created for this job
        cursor.execute("SELECT id, invoice_no FROM invoices WHERE job_id = ? AND status != 'CANCELLED';", (job_id,))
        existing_inv = cursor.fetchone()
        if existing_inv:
            conn.rollback()
            return {"success": True, "already_exists": True, "invoice_id": existing_inv["id"], "invoice_no": existing_inv["invoice_no"], "message": f"Invois {existing_inv['invoice_no']} telah sedia wujud untuk kerja ini."}

        # Generate invoice number and QR token
        invoice_no = generate_reference_no("INV-", "invoices", "invoice_no")
        qr_token = generate_qr_token()

        subtotal = float(job["parts_total"]) + float(job["materials_total"]) + float(job["labour_total"])
        discount = float(job["discount"])
        tax = 0.0 # Default SST disabled
        grand_total = max(0.0, round(subtotal - discount + tax, 2))
        balance_due = grand_total

        cursor.execute("""
            INSERT INTO invoices (invoice_no, job_id, customer_id, vehicle_id, service_type, subtotal, discount, tax, grand_total, deposit_amount, paid_amount, balance_due, status, qr_token, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, ?, 'DRAFT', ?, ?, ?);
        """, (invoice_no, job_id, job["customer_id"], job["vehicle_id"], job["service_type"], subtotal, discount, tax, grand_total, balance_due, qr_token, job["notes"], user.get("id")))
        invoice_id = cursor.lastrowid

        # Copy job items to invoice lines
        cursor.execute("SELECT * FROM job_items WHERE job_id = ?;", (job_id,))
        items = cursor.fetchall()
        for item in items:
            cursor.execute("""
                INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (invoice_id, item["item_type"], item["inventory_id"], item["sku"], item["name"], item["qty"], item["unit_price"], item["amount"]))

        # Log audit
        cursor.execute("""
            INSERT INTO audit_logs (user_id, user_name, role, action, module, record_id, new_value)
            VALUES (?, ?, ?, 'JOB_CONVERTED_TO_INVOICE', 'INVOICE', ?, ?);
        """, (user.get("id"), user.get("name"), user.get("role"), str(invoice_id),
              json.dumps({"job_id": job_id, "invoice_no": invoice_no, "total": grand_total})))

        conn.commit()
        return {"success": True, "invoice_id": invoice_id, "invoice_no": invoice_no, "grand_total": grand_total, "qr_token": qr_token}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Ralat menukar kad kerja ke invois: {str(e)}"}
    finally:
        conn.close()

def convert_quotation_to_job(quotation_id: int, user: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an accepted quotation into an active Work Order / Job Card."""
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM quotations WHERE id = ?;", (quotation_id,))
        quote = cursor.fetchone()
        if not quote:
            conn.rollback()
            return {"success": False, "error": "Sebut harga tidak ditemui."}

        job_no = generate_reference_no("JOB-", "jobs", "job_no")

        # Calculate totals from quotation lines
        cursor.execute("SELECT * FROM quotation_lines WHERE quotation_id = ?;", (quotation_id,))
        lines = cursor.fetchall()

        parts_total = sum(l["amount"] for l in lines if l["item_type"] == "PART")
        materials_total = sum(l["amount"] for l in lines if l["item_type"] == "MATERIAL")
        labour_total = sum(l["amount"] for l in lines if l["item_type"] == "LABOUR")
        estimated_total = parts_total + materials_total + labour_total - float(quote["discount"])

        cursor.execute("""
            INSERT INTO jobs (job_no, service_type, customer_id, vehicle_id, complaint, inspection, diagnosis, status, parts_total, materials_total, labour_total, discount, estimated_total, notes, created_by)
            VALUES (?, ?, ?, ?, 'Berdasarkan Sebut Harga', 'Pemeriksaan Awal', 'Kerja Mengikut Sebut Harga', 'IN_PROGRESS', ?, ?, ?, ?, ?, ?, ?);
        """, (job_no, quote["service_type"], quote["customer_id"], quote["vehicle_id"], parts_total, materials_total, labour_total, quote["discount"], estimated_total, quote["notes"], user.get("id")))
        job_id = cursor.lastrowid

        for line in lines:
            cursor.execute("""
                INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (job_id, line["item_type"], line["inventory_id"], line["sku"], line["description"], line["qty"], line["unit_price"], line["amount"]))

        # Update quotation status to ACCEPTED
        cursor.execute("UPDATE quotations SET status = 'ACCEPTED', updated_at = CURRENT_TIMESTAMP WHERE id = ?;", (quotation_id,))

        conn.commit()
        return {"success": True, "job_id": job_id, "job_no": job_no, "estimated_total": estimated_total}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Ralat menukar sebut harga ke kad kerja: {str(e)}"}
    finally:
        conn.close()

def purge_demo_data_transaction(user: Dict[str, Any]) -> Dict[str, Any]:
    """Admin-only: Purge all demo records safely without deleting real data or company settings."""
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        cursor = conn.cursor()

        # Delete dependent demo records first
        cursor.execute("DELETE FROM receipts WHERE is_demo = 1;")
        cursor.execute("DELETE FROM payments WHERE is_demo = 1;")
        cursor.execute("DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE is_demo = 1);")
        cursor.execute("DELETE FROM invoices WHERE is_demo = 1;")
        cursor.execute("DELETE FROM job_images WHERE job_id IN (SELECT id FROM jobs WHERE is_demo = 1);")
        cursor.execute("DELETE FROM job_items WHERE job_id IN (SELECT id FROM jobs WHERE is_demo = 1);")
        cursor.execute("DELETE FROM jobs WHERE is_demo = 1;")
        cursor.execute("DELETE FROM quotation_lines WHERE quotation_id IN (SELECT id FROM quotations WHERE is_demo = 1);")
        cursor.execute("DELETE FROM quotations WHERE is_demo = 1;")
        cursor.execute("DELETE FROM purchase_items WHERE purchase_id IN (SELECT id FROM purchases WHERE is_demo = 1);")
        cursor.execute("DELETE FROM purchases WHERE is_demo = 1;")
        cursor.execute("DELETE FROM stock_movements WHERE is_demo = 1;")
        cursor.execute("DELETE FROM inventory WHERE is_demo = 1;")
        cursor.execute("DELETE FROM vehicles WHERE is_demo = 1;")
        cursor.execute("DELETE FROM customers WHERE is_demo = 1;")
        cursor.execute("DELETE FROM suppliers WHERE is_demo = 1;")

        # Audit log
        cursor.execute("""
            INSERT INTO audit_logs (user_id, user_name, role, action, module, record_id, new_value)
            VALUES (?, ?, ?, 'PURGE_DEMO_DATA', 'SETTINGS', 'SYSTEM', ?);
        """, (user.get("id"), user.get("name"), user.get("role"), json.dumps({"action": "All demo data removed successfully"})))

        conn.commit()
        return {"success": True, "message": "Semua data demo telah berjaya dipadamkan. Tetapan dan rekod sebenar dikekalkan."}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": f"Ralat memadam data demo: {str(e)}"}
    finally:
        conn.close()
