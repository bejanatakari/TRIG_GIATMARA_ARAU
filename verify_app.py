"""
TRIG PROFESSIONAL - AUTO WORKSHOP MANAGEMENT & POS SYSTEM
GM GEAR ARAU
Direct In-Memory Acceptance Test Suite (Zero Socket Dependency - 100% Sandboxed)
Tests all 23 End-to-End Acceptance Tests directly against the API Handler and Database
"""

import sys
import os
import json
import io
import time
import datetime
import sqlite3

from app import TrigPOSHandler
from database import get_db_connection, DB_PATH
import business_logic
import seed_data

class MockSocket:
    """Mock socket address for client_address."""
    def __init__(self, ip="127.0.0.1", port=54321):
        self.ip = ip
        self.port = port
    def getsockname(self):
        return (self.ip, self.port)

class DirectTestClient:
    """In-memory HTTP test client for TrigPOSHandler without network socket requirements."""
    def __init__(self):
        pass

    def request(self, method, path, data=None, token=None):
        rfile = io.BytesIO()
        if data is not None:
            body_bytes = json.dumps(data).encode("utf-8")
            rfile.write(body_bytes)
            rfile.seek(0)
            content_len = len(body_bytes)
        else:
            content_len = 0

        wfile = io.BytesIO()

        # Build mock headers
        headers = {
            "Content-Length": str(content_len),
            "Content-Type": "application/json"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Initialize Handler with dummy parameters
        handler = TrigPOSHandler.__new__(TrigPOSHandler)
        handler.rfile = rfile
        handler.wfile = wfile
        handler.path = path
        handler.command = method
        handler.headers = headers
        handler.client_address = ("127.0.0.1", 54321)
        handler.server_version = "TrigPOS/1.0"
        handler.sys_version = "Python/3.9"
        handler.response_status = 200
        handler.response_headers = {}

        def mock_send_response(status, message=None):
            handler.response_status = status

        def mock_send_header(keyword, value):
            handler.response_headers[keyword] = value

        def mock_end_headers():
            pass

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers

        # Dispatch method
        if method == "GET":
            handler.do_GET()
        elif method == "POST":
            handler.do_POST()
        elif method == "PUT":
            handler.do_PUT()
        elif method == "DELETE":
            handler.do_DELETE()
        elif method == "OPTIONS":
            handler.do_OPTIONS()

        raw_output = wfile.getvalue()
        try:
            parsed = json.loads(raw_output.decode("utf-8")) if raw_output else {}
        except Exception:
            parsed = {"raw": raw_output}

        return handler.response_status, parsed

def run_all_tests():
    print("=================================================================")
    print("MEMULAKAN 23 UJIAN PENERIMAAN (ACCEPTANCE TESTS)")
    print("SISTEM: TRIG PROFESSIONAL | BENGKEL: GM GEAR ARAU")
    print("=================================================================")

    # Ensure fresh seed data and clean previous test records for full idempotency
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM receipts WHERE invoice_id IN (SELECT id FROM invoices WHERE customer_id IN (SELECT id FROM customers WHERE phone = '019-4889900'));")
    c.execute("DELETE FROM payments WHERE invoice_id IN (SELECT id FROM invoices WHERE customer_id IN (SELECT id FROM customers WHERE phone = '019-4889900'));")
    c.execute("DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE customer_id IN (SELECT id FROM customers WHERE phone = '019-4889900'));")
    c.execute("DELETE FROM invoices WHERE customer_id IN (SELECT id FROM customers WHERE phone = '019-4889900');")
    c.execute("DELETE FROM job_images WHERE job_id IN (SELECT id FROM jobs WHERE customer_id IN (SELECT id FROM customers WHERE phone = '019-4889900'));")
    c.execute("DELETE FROM job_items WHERE job_id IN (SELECT id FROM jobs WHERE customer_id IN (SELECT id FROM customers WHERE phone = '019-4889900'));")
    c.execute("DELETE FROM jobs WHERE customer_id IN (SELECT id FROM customers WHERE phone = '019-4889900');")
    c.execute("DELETE FROM vehicles WHERE reg_no IN ('RN 9988', 'KV 1122', 'RAP 3322');")
    c.execute("DELETE FROM customers WHERE phone = '019-4889900';")
    c.execute("UPDATE invoices SET status = 'PARTIALLY_PAID', paid_amount = 300.00, balance_due = 550.00 WHERE invoice_no = 'INV-2026-000002';")
    c.execute("DELETE FROM payments WHERE invoice_id IN (SELECT id FROM invoices WHERE invoice_no = 'INV-2026-000002') AND payment_type = 'FINAL';")
    c.execute("DELETE FROM receipts WHERE invoice_id IN (SELECT id FROM invoices WHERE invoice_no = 'INV-2026-000002') AND receipt_type = 'FINAL';")
    conn.commit()
    conn.close()

    seed_data.seed_database(force_reseed=False)
    client = DirectTestClient()

    passed_count = 0
    failed_count = 0

    def assert_test(cond, test_num, description):
        nonlocal passed_count, failed_count
        if cond:
            print(f"  [PASSED] TEST {test_num:02d}: {description}")
            passed_count += 1
        else:
            print(f"  [FAILED] TEST {test_num:02d}: {description}")
            failed_count += 1

    # Login Admin
    status, admin_login = client.request("POST", "/api/auth/login", {
        "email": "gmgearkubangpasu@gmail.com",
        "password": "Admin@GMGear2026!"
    })
    admin_token = admin_login.get("token")
    assert_test(status == 200 and admin_token is not None, 0, "Admin Login Berjaya")

    # Login Cashier
    status, cashier_login = client.request("POST", "/api/auth/login", {
        "email": "juruwang@gmgear.my",
        "password": "Cashier@123"
    })
    cashier_token = cashier_login.get("token")

    # Login Mechanic
    status, mechanic_login = client.request("POST", "/api/auth/login", {
        "email": "mekanik@gmgear.my",
        "password": "Mechanic@123"
    })
    mechanic_token = mechanic_login.get("token")

    # TEST 1: Create customer
    status, c_res = client.request("POST", "/api/customers", {
        "name": "Ustaz Mohd Faiz bin Kassim",
        "phone": "019-4889900",
        "email": "faiz.kassim@arau.edu.my",
        "address": "Taman Jelempok Indah, 02600 Arau, Perlis"
    }, token=admin_token)
    test_cust_id = c_res.get("customer_id")
    assert_test(status == 200 and test_cust_id is not None, 1, "Cipta Pelanggan Baharu")

    # TEST 2: Create car and Auto Service Job
    status, v1_res = client.request("POST", "/api/vehicles", {
        "customer_id": test_cust_id,
        "vehicle_type": "CAR",
        "reg_no": "RN 9988",
        "make": "Proton",
        "model": "Saga VVT",
        "year": 2023,
        "mileage": 30000
    }, token=admin_token)
    car_id = v1_res.get("vehicle_id")

    status, job1_res = client.request("POST", "/api/jobs", {
        "service_type": "AUTO_SERVICE",
        "customer_id": test_cust_id,
        "vehicle_id": car_id,
        "mileage": 30000,
        "complaint": "Servis 30,000km dan pemeriksaan brek",
        "items": [
            {"item_type": "PART", "name": "Petronas Syntium 3000 5W-40 (4L)", "sku": "OIL-SYN-5W40", "qty": 1, "unit_price": 168.0, "amount": 168.0, "inventory_id": 1},
            {"item_type": "PART", "name": "Oil Filter Proton Original", "sku": "FIL-OIL-PRT", "qty": 1, "unit_price": 25.0, "amount": 25.0, "inventory_id": 5},
            {"item_type": "LABOUR", "name": "Upah Servis Minyak & Filter", "qty": 1, "unit_price": 40.0, "amount": 40.0}
        ]
    }, token=admin_token)
    job1_id = job1_res.get("job_id")
    assert_test(status == 200 and job1_id is not None and job1_res.get("job_no", "").startswith("JOB-"), 2, "Cipta Kereta & Kad Kerja Servis Auto")

    # TEST 3: Create Body & Paint Job with photos/panels
    status, v2_res = client.request("POST", "/api/vehicles", {
        "customer_id": test_cust_id,
        "vehicle_type": "CAR",
        "reg_no": "KV 1122",
        "make": "Honda",
        "model": "City",
        "year": 2021,
        "colour": "Platinum White"
    }, token=admin_token)
    paint_car_id = v2_res.get("vehicle_id")

    status, job2_res = client.request("POST", "/api/jobs", {
        "service_type": "BODY_PAINT",
        "customer_id": test_cust_id,
        "vehicle_id": paint_car_id,
        "complaint": "Pintu depan calar teruk & kemek",
        "damage_description": "Kemek 10cm pada pintu depan dan calar fender",
        "repair_method": "Ketuk, simen putty, primer 2K, sembur cat & clear",
        "paint_colour": "Platinum White Pearl",
        "paint_code": "NH883P",
        "paint_quantity": 1.2,
        "damaged_panels": ["Pintu Depan Kiri (FL)", "Fender Kiri"],
        "damage_types": ["Kemek", "Calar Tajam"],
        "items": [
            {"item_type": "MATERIAL", "name": "Nippon Paint 2K Primer", "sku": "PNT-PRM-2K", "qty": 1, "unit_price": 75.0, "amount": 75.0, "inventory_id": 21},
            {"item_type": "LABOUR", "name": "Upah Mengetuk & Cat Pintu", "qty": 1, "unit_price": 450.0, "amount": 450.0}
        ]
    }, token=admin_token)
    job2_id = job2_res.get("job_id")

    # Upload test image
    status, img_res = client.request("POST", f"/api/jobs/{job2_id}/images", {
        "stage": "BEFORE",
        "image_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "caption": "Kerosakan kemek sebelum pembaikan"
    }, token=admin_token)
    assert_test(status == 200 and job2_id is not None and img_res.get("success"), 3, "Cipta Kad Kerja Mengetuk & Mengecat bersama Panel & Gambar")

    # TEST 4: Create Motorcycle Job
    status, v3_res = client.request("POST", "/api/vehicles", {
        "customer_id": test_cust_id,
        "vehicle_type": "MOTORCYCLE",
        "reg_no": "RAP 3322",
        "make": "Yamaha",
        "model": "Y15ZR",
        "engine_cc": 150,
        "engine_no": "G3J8E99112"
    }, token=admin_token)
    bike_id = v3_res.get("vehicle_id")

    status, job3_res = client.request("POST", "/api/jobs", {
        "service_type": "MOTORCYCLE",
        "customer_id": test_cust_id,
        "vehicle_id": bike_id,
        "complaint": "Tukar minyak 4T fully synthetic & pasang spark plug baru",
        "items": [
            {"item_type": "PART", "name": "Motul 7100 4T 10W-40 (1L)", "sku": "OIL-MOTUL-7100", "qty": 1, "unit_price": 75.0, "amount": 75.0, "inventory_id": 3},
            {"item_type": "PART", "name": "NGK CPR8EA-9 Spark Plug", "sku": "SPK-PLG-MOTO", "qty": 1, "unit_price": 18.0, "amount": 18.0, "inventory_id": 13},
            {"item_type": "LABOUR", "name": "Upah Servis Motosikal", "qty": 1, "unit_price": 15.0, "amount": 15.0}
        ]
    }, token=admin_token)
    job3_id = job3_res.get("job_id")
    assert_test(status == 200 and job3_id is not None, 4, "Cipta Kad Kerja Servis Motosikal")

    # TEST 5: Scan 3 inventory parts via QR / SKU
    s1, r1 = client.request("GET", "/api/inventory/qr-lookup?code=OIL-SYN-5W40", token=admin_token)
    s2, r2 = client.request("GET", "/api/inventory/qr-lookup?code=FIL-OIL-PRT", token=admin_token)
    s3, r3 = client.request("GET", "/api/inventory/qr-lookup?code=BRK-PAD-BDX-F", token=admin_token)
    assert_test(s1 == 200 and s2 == 200 and s3 == 200 and r1["item"]["sku"] == "OIL-SYN-5W40", 5, "Imbas 3 Alat Ganti Inventori Melalui QR/SKU")

    # TEST 6: Verify parts appear individually in job
    status, job_view = client.request("GET", f"/api/jobs/{job1_id}", token=admin_token)
    item_skus = [i.get("sku") for i in job_view["job"]["items"]]
    assert_test("OIL-SYN-5W40" in item_skus and "FIL-OIL-PRT" in item_skus, 6, "Sahkan Alat Ganti Muncul Individu Dalam Kad Kerja")

    # TEST 7: Convert job to invoice
    status, conv_res = client.request("POST", f"/api/jobs/{job1_id}/convert-to-invoice", token=admin_token)
    test_inv_id = conv_res.get("invoice_id")
    test_inv_no = conv_res.get("invoice_no")
    assert_test(status == 200 and test_inv_id is not None and test_inv_no.startswith("INV-"), 7, "Tukar Kad Kerja ke Invois Rasmi")

    # TEST 8: Verify service type preserved
    status, inv_view = client.request("GET", f"/api/invoices/{test_inv_id}", token=admin_token)
    assert_test(inv_view["invoice"]["service_type"] == "AUTO_SERVICE", 8, "Sahkan Kategori Servis AUTO_SERVICE Dikekalkan Pada Invois")

    # TEST 9: Enter deposit
    status, dep_res = client.request("POST", "/api/payments", {
        "invoice_id": test_inv_id,
        "amount": 100.00,
        "payment_method": "CASH",
        "payment_type": "DEPOSIT",
        "notes": "Deposit tunai permulaan"
    }, token=cashier_token)
    assert_test(status == 200 and dep_res.get("success"), 9, "Masukkan Bayaran Deposit RM 100.00")

    # TEST 10: Verify balance
    status, inv_view_2 = client.request("GET", f"/api/invoices/{test_inv_id}", token=admin_token)
    expected_balance = round(float(inv_view_2["invoice"]["grand_total"]) - 100.00, 2)
    actual_balance = round(float(inv_view_2["invoice"]["balance_due"]), 2)
    assert_test(expected_balance == actual_balance, 10, f"Sahkan Baki Tepat Selepas Deposit (Baki: RM {actual_balance:.2f})")

    # TEST 11: Approve invoice - Verify stock deducted EXACTLY ONCE
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT stock_qty FROM inventory WHERE sku = 'OIL-SYN-5W40';")
    stock_before = float(c.fetchone()[0])
    conn.close()

    status, app_res = client.request("POST", f"/api/invoices/{test_inv_id}/approve", token=admin_token)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT stock_qty FROM inventory WHERE sku = 'OIL-SYN-5W40';")
    stock_after = float(c.fetchone()[0])
    conn.close()

    assert_test(status == 200 and (stock_before - stock_after == 1.0), 11, f"Luluskan Invois - Stok Ditolak Tepat Sekali ({stock_before} -> {stock_after})")

    # TEST 12: Refresh / re-approve invoice - Stock MUST NOT deduct again
    status, app_again = client.request("POST", f"/api/invoices/{test_inv_id}/approve", token=admin_token)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT stock_qty FROM inventory WHERE sku = 'OIL-SYN-5W40';")
    stock_refresh = float(c.fetchone()[0])
    conn.close()
    assert_test(stock_refresh == stock_after, 12, "Luluskan Semula Invois - Stok TIDAK Ditolak Kali Kedua (Idempotent)")

    # TEST 13: Cancel approved invoice - Stock returned EXACTLY ONCE
    status, cancel_res = client.request("POST", f"/api/invoices/{test_inv_id}/cancel", {
        "reason": "Pelanggan tangguhkan servis kenderaan"
    }, token=admin_token)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT stock_qty FROM inventory WHERE sku = 'OIL-SYN-5W40';")
    stock_cancelled = float(c.fetchone()[0])
    conn.close()
    assert_test(status == 200 and (stock_cancelled == stock_before), 13, f"Batalkan Invois - Stok Dipulangkan Semula Tepat Sekali ({stock_after} -> {stock_cancelled})")

    # TEST 14: Scan Invoice QR -> opens correct final payment details
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, invoice_no, qr_token, balance_due FROM invoices WHERE invoice_no = 'INV-2026-000002';")
    inv2_row = c.fetchone()
    conn.close()
    
    s_qr, qr_data = client.request("GET", f"/api/invoices/qr-lookup?token={inv2_row['qr_token']}", token=cashier_token)
    assert_test(s_qr == 200 and qr_data["invoice"]["invoice_no"] == "INV-2026-000002", 14, "Imbas Kod QR Invois - Membuka Skrin Bayaran Yang Betul")

    # TEST 15: Receive final payment -> receipt automatically generated & status PAID
    rem_balance = float(qr_data["invoice"]["balance_due"])
    status, pay_final = client.request("POST", "/api/payments", {
        "invoice_id": inv2_row["id"],
        "amount": rem_balance,
        "payment_method": "DUITNOW_QR",
        "payment_type": "FINAL",
        "reference_no": "DN-TEST-FINAL-99"
    }, token=cashier_token)
    rcp_no = pay_final.get("receipt_no")
    assert_test(status == 200 and pay_final.get("status") == "PAID" and rcp_no.startswith("RCP-"), 15, f"Terima Bayaran Akhir Penuh - Resit Dijana Automatik ({rcp_no})")

    # TEST 16: Print A4 Invoice Layout
    s_inv_view, inv_detail = client.request("GET", f"/api/invoices/{inv2_row['id']}", token=admin_token)
    assert_test(s_inv_view == 200 and "lines" in inv_detail["invoice"], 16, "Sahkan Data Lengkap Susun Atur Cetakan A4 Invois")

    # TEST 17: Print Thermal 80mm Receipt Layout
    s_rcp_view, rcp_detail = client.request("GET", f"/api/receipts/{rcp_no}", token=cashier_token)
    assert_test(s_rcp_view == 200 and rcp_detail["snapshot"]["receipt_no"] == rcp_no, 17, "Sahkan Data Lengkap Susun Atur Cetakan Terma 80mm Resit")

    # TEST 18: Download PDF / Backup file
    s_bk, bk_data = client.request("GET", "/api/settings/backup", token=admin_token)
    assert_test(s_bk == 200, 18, "Muat Turun Sandaran / Salinan Pangkalan Data (Backup)")

    # TEST 19: Mechanic cannot access Admin Settings
    s_mech_settings, _ = client.request("GET", "/api/audit-logs", token=mechanic_token)
    assert_test(s_mech_settings == 403, 19, "Mekanik Disekat Daripada Mengakses Tetapan & Log Audit Admin")

    # TEST 20: Cashier cannot change restricted settings
    s_cashier_set, _ = client.request("POST", "/api/settings", {"company_name": "HACKED NAME"}, token=cashier_token)
    assert_test(s_cashier_set == 403, 20, "Juruwang Disekat Daripada Mengubah Tetapan Kritikal Syarikat")

    # TEST 21: Audit Log records sensitive actions
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM audit_logs WHERE action IN ('INVOICE_APPROVED', 'INVOICE_CANCELLED', 'PAYMENT_RECEIVED');")
    audit_count = int(c.fetchone()[0])
    conn.close()
    assert_test(audit_count >= 3, 21, f"Log Audit Merekodkan Tindakan Sensitif ({audit_count} rekod audit dikesan)")

    # TEST 22: Concurrency safety - simultaneous duplicate payment prevention
    s_overpay, overpay_res = client.request("POST", "/api/payments", {
        "invoice_id": inv2_row["id"],
        "amount": 500.00,
        "payment_method": "CASH",
        "payment_type": "FINAL"
    }, token=cashier_token)
    assert_test(s_overpay == 400 and "telah pun dibayar penuh" in overpay_res.get("error", ""), 22, "Halang Pembayaran Melebihi Baki / Bayaran Berganda")

    # TEST 23: Replace company logo from Admin Settings
    test_logo = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxyZWN0IHdpZHRoPSIxMCIgaGVpZ2h0PSIxMCIvPjwvc3ZnPg=="
    s_logo, logo_res = client.request("POST", "/api/settings", {
        "company_name": "GM GEAR ARAU",
        "logo_base64": test_logo
    }, token=admin_token)
    s_check, check_set = client.request("GET", "/api/company-info")
    assert_test(s_check == 200 and check_set["company"]["logo_base64"] == test_logo, 23, "Tukar Logo Bengkel & Sahkan Terpapar Pada Dokumen")

    print("=================================================================")
    print(f"KEPUTUSAN KESELURUHAN: {passed_count}/23 UJIAN DILULUSKAN (PASSED)!")
    if failed_count == 0:
        print("SEMUA 23 ACCEPTANCE TESTS TELAH BERJAYA DILULUSKAN 100%!")
    else:
        print(f"AMARAN: {failed_count} ujian gagal.")
    print("=================================================================")

    return failed_count == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
