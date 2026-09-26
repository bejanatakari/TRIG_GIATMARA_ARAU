"""
TRIG PROFESSIONAL - AUTO WORKSHOP MANAGEMENT & POS SYSTEM
GM GEAR ARAU
Seed Data Module: Generates realistic Malaysian Demo Data and Initial Admin User
"""

import sqlite3
import datetime
import json
from database import get_db_connection, hash_password
from business_logic import generate_qr_token

def seed_database(force_reseed=False):
    """Seed initial company, users, and comprehensive demo dataset."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Company Settings
    cursor.execute("SELECT COUNT(*) FROM company_settings WHERE id = 1;")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO company_settings (id, company_name, trading_name, reg_no, phone, email, address, currency, tax_enabled, tax_rate)
            VALUES (1, 'GM GEAR ARAU', 'GM GEAR ARAU (Bengkel Automotif & Mengecat)', '202403123456 (003123456-X)', '019-4567890', 'gmgearkubangpasu@gmail.com', 'No. 12, Jalan Arau Indah, 02600 Arau, Perlis', 'RM', 0, 6.0);
        """)

    # 2. Users (Admin, Cashier, Mechanic)
    cursor.execute("SELECT COUNT(*) FROM users WHERE email = 'gmgearkubangpasu@gmail.com';")
    if cursor.fetchone()[0] == 0:
        admin_hash, admin_salt = hash_password("Admin@GMGear2026!")
        cashier_hash, cashier_salt = hash_password("Cashier@123")
        mechanic_hash, mechanic_salt = hash_password("Mechanic@123")

        cursor.execute("""
            INSERT INTO users (name, email, password_hash, salt, role, phone)
            VALUES ('Pengurus Utama (Admin)', 'gmgearkubangpasu@gmail.com', ?, ?, 'ADMIN', '019-4567890');
        """, (admin_hash, admin_salt))
        admin_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO users (name, email, password_hash, salt, role, phone)
            VALUES ('Siti Juruwang', 'juruwang@gmgear.my', ?, ?, 'CASHIER', '017-8899001');
        """, (cashier_hash, cashier_salt))
        cashier_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO users (name, email, password_hash, salt, role, phone)
            VALUES ('Pak Tam Mekanik', 'mekanik@gmgear.my', ?, ?, 'MECHANIC', '012-3344556');
        """, (mechanic_hash, mechanic_salt))
        mechanic_id = cursor.lastrowid
    else:
        cursor.execute("SELECT id FROM users WHERE email = 'gmgearkubangpasu@gmail.com';")
        admin_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM users WHERE email = 'juruwang@gmgear.my';")
        r = cursor.fetchone()
        cashier_id = r[0] if r else admin_id
        cursor.execute("SELECT id FROM users WHERE email = 'mekanik@gmgear.my';")
        r = cursor.fetchone()
        mechanic_id = r[0] if r else admin_id

    # Check if demo data already seeded
    cursor.execute("SELECT COUNT(*) FROM customers WHERE is_demo = 1;")
    if cursor.fetchone()[0] > 0 and not force_reseed:
        conn.commit()
        conn.close()
        return

    print("Memulakan penjanaan Data Demo GM GEAR ARAU...")

    # 3. Suppliers (5 Pembekal Automotif)
    suppliers_data = [
        ("Perlis Auto Spares Sdn Bhd", "En. Roslan Bakar", "019-4112233", "roslan@perlisauto.com.my", "Kawasan Perindustrian Jejawi, 02600 Arau, Perlis"),
        ("UMW Lubricants & Oil Dist.", "Pn. Lee Mei Ling", "012-4455667", "orders@umwlubricants.my", "Jalan Tandop, 05400 Alor Setar, Kedah"),
        ("Glasurit & Nippon Paint Supplies", "Mr. David Tan", "016-7788990", "sales@glasuritpaint.com", "Bukit Mertajam Industrial Zone, Penang"),
        ("Utara Tyre & Battery Specialist", "Hj. Ismail Hashim", "013-5566778", "utara.tyres@gmail.com", "Pusat Perniagaan Arau, 02600 Arau, Perlis"),
        ("RK & DID Motorcycle Spares Hub", "Mr. Kevin Chong", "017-6655443", "support@rkspares.my", "Sungai Petani Industrial Area, Kedah")
    ]
    supplier_ids = []
    for s in suppliers_data:
        cursor.execute("""
            INSERT INTO suppliers (company, contact_person, phone, email, address, is_demo)
            VALUES (?, ?, ?, ?, ?, 1);
        """, s)
        supplier_ids.append(cursor.lastrowid)

    # 4. Customers (10 Pelanggan Malaysia)
    customers_data = [
        ("Ahmad Danial bin Razak", "880512-02-5431", "012-4567891", "012-4567891", "danial@gmail.com", "No 15, Taman Arau Idaman, 02600 Arau, Perlis"),
        ("Tan Wei Ming", "790423-08-5123", "016-4321987", "016-4321987", "weiming.tan@outlook.com", "No 88, Jalan Pegawai, 01000 Kangar, Perlis"),
        ("Muthu A/L Raman", "851105-02-6019", "017-5544332", "017-5544332", "muthu_raman@yahoo.com", "Lot 45, Kampung Guar Nangka, 02500 Mata Ayer, Perlis"),
        ("Siti Nurhaliza binti Kamal", "920314-02-5882", "013-4499112", "013-4499112", "siti.kamal@gmail.com", "No 22, Taman Pauh Jaya, 02600 Pauh, Perlis"),
        ("Muhammad Hafiz bin Othman", "950820-02-5111", "019-5566778", "019-5566778", "hafiz.othman@gmail.com", "No 3, Lorong Seri Melati, 02600 Arau, Perlis"),
        ("Jason Lee Boon Hock", "901201-07-5321", "014-9988776", "014-9988776", "jasonlee@techmy.com", "No 12A, Taman Universiti, 02600 Kubang Gajah, Perlis"),
        ("Nurul Ain binti Zulkifli", "960618-09-5022", "011-22334455", "011-22334455", "nurulain96@gmail.com", "No 50, Taman Tambun Tulang, 02700 Simpang Empat, Perlis"),
        ("Chong Kok Keong", "810115-08-5433", "016-7711223", "016-7711223", "keong.chong@gmail.com", "No 7, Medan Niaga Kangar, 01000 Kangar, Perlis"),
        ("Azman bin Ibrahim", "750708-02-5091", "019-3322114", "019-3322114", "azman.ibrahim@felda.net.my", "Peringkat 2, Felda Chuping, 02500 Chuping, Perlis"),
        ("Kavitha Devi A/P Suresh", "930928-02-5984", "018-9900112", "018-9900112", "kavitha.suresh@gmail.com", "No 19, Taman Sena Indah, 01000 Kangar, Perlis")
    ]
    customer_ids = []
    for c in customers_data:
        cursor.execute("""
            INSERT INTO customers (name, ic_company, phone, whatsapp, email, address, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, 1);
        """, c)
        customer_ids.append(cursor.lastrowid)

    # 5. Vehicles (8 Cars & 5 Motorcycles)
    cars_data = [
        (customer_ids[0], "CAR", "RR 1234", "Proton", "X50", "1.5 TGDI Flagship", 2022, "1.5L Turbo", 1477, "3G15TD89211", "PL1X50TGDI202201", "Automatic", 42500, "Ocean Blue", "B99", "Petrol"),
        (customer_ids[1], "CAR", "KV 5678", "Perodua", "Myvi", "1.5 H", 2021, "2NR-VE", 1496, "2NR998124", "PM2M15H202108", "Automatic", 58300, "Glittering Silver", "S28", "Petrol"),
        (customer_ids[2], "CAR", "PK 9012", "Honda", "Civic", "1.5 VTEC Turbo RS", 2023, "L15B7", 1498, "L15B782190", "MHRFE1880NJ1022", "CVT", 26100, "Ignite Red", "R575M", "Petrol"),
        (customer_ids[3], "CAR", "RL 3456", "Toyota", "Vios", "1.5 G", 2020, "2NR-FE", 1496, "2NRFE44321", "MR053BYG901234", "CVT", 71200, "Platinum White Pearl", "089", "Petrol"),
        (customer_ids[4], "CAR", "RN 7890", "Proton", "Saga", "1.3 Premium VVT", 2022, "CamPro VVT", 1332, "SAGA133290", "PL1BT13VVT2022", "Automatic", 35400, "Ruby Red", "R44", "Petrol"),
        (customer_ids[5], "CAR", "KA 2345", "Nissan", "Almera", "1.0 Turbo VLP", 2021, "HR10DET", 999, "HR10DET5541", "JN1TDA10T2021", "CVT", 49800, "Monarch Orange", "EBD", "Petrol"),
        (customer_ids[6], "CAR", "RP 6789", "Perodua", "Alza", "1.5 AV", 2023, "2NR-VE", 1496, "2NRVE88712", "PM2W15AV2023", "D-CVT", 18900, "Vintage Brown", "R72", "Petrol"),
        (customer_ids[7], "CAR", "KD 8901", "Honda", "HR-V", "1.5 Turbo V", 2022, "L15C3", 1498, "L15C301988", "MHRRV3860PJ001", "CVT", 39100, "Meteoroid Gray", "NH904M", "Petrol")
    ]
    car_ids = []
    for cd in cars_data:
        cursor.execute("""
            INSERT INTO vehicles (customer_id, vehicle_type, reg_no, make, model, variant, year, engine, engine_cc, engine_no, chassis_vin, transmission, mileage, colour, colour_code, fuel_type, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
        """, cd)
        car_ids.append(cursor.lastrowid)

    bikes_data = [
        (customer_ids[8], "MOTORCYCLE", "RAP 8819", "Yamaha", "Y15ZR", "V2 Doxou", 2021, "4-Stroke SOHC", 150, "G3J8E009182", "MH3SG4810K00918", "Manual 5-Speed", 28500, "Matte Cyan", "CY1", "Petrol"),
        (customer_ids[9], "MOTORCYCLE", "KCK 4432", "Honda", "RS150R", "Repsol Edition", 2020, "DOHC 4-Valve", 149, "K56E109823", "MH1K56108LK1098", "Manual 6-Speed", 39400, "Orange/White Repsol", "REP", "Petrol"),
        (customer_ids[0], "MOTORCYCLE", "RAA 1010", "Yamaha", "NVX 155", "ABS Standard", 2023, "BlueCore VVA", 155, "G3L4E012399", "MH3SG5620P01239", "Automatic", 14200, "Silver Petrol", "SLV", "Petrol"),
        (customer_ids[3], "MOTORCYCLE", "KDH 7721", "Modenas", "Kriss 110", "Disc Brake", 2019, "SOHC Air-Cooled", 110, "AN110E9812", "PM3AN110DK1981", "Rotary 4-Speed", 51200, "Metallic Blue", "BLU", "Petrol"),
        (customer_ids[4], "MOTORCYCLE", "RAB 5505", "Honda", "EX5", "Dream Fi 35th Anniv", 2022, "PGM-Fi OHC", 110, "K09E219801", "MH1K09104MK2198", "Rotary 4-Speed", 22100, "Extravagant Gold", "GLD", "Petrol")
    ]
    bike_ids = []
    for bd in bikes_data:
        cursor.execute("""
            INSERT INTO vehicles (customer_id, vehicle_type, reg_no, make, model, variant, year, engine, engine_cc, engine_no, chassis_vin, transmission, mileage, colour, colour_code, fuel_type, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
        """, bd)
        bike_ids.append(cursor.lastrowid)

    # 6. Inventory Items (30 items across mechanical, paint, motorcycle, lubricants, consumables)
    items_data = [
        # SKU, QR_ID, Name, Category, Brand, SupplierIdx, Cost, Sell, Stock, MinStock, Reorder, Location, Unit
        ("OIL-SYN-5W40", "QR-INV-0001", "Petronas Syntium 3000 5W-40 (4L)", "Lubricants", "Petronas", 1, 110.00, 168.00, 18.0, 5.0, 15.0, "Rak A-1", "BOTTLE"),
        ("OIL-MAG-10W40", "QR-INV-0002", "Castrol Magnatec 10W-40 (4L)", "Lubricants", "Castrol", 1, 85.00, 135.00, 14.0, 5.0, 12.0, "Rak A-2", "BOTTLE"),
        ("OIL-MOTUL-7100", "QR-INV-0003", "Motul 7100 4T 10W-40 100% Synthetic (1L)", "Motorcycle Parts", "Motul", 1, 48.00, 75.00, 25.0, 8.0, 20.0, "Rak A-3", "BOTTLE"),
        ("OIL-SHELL-AX7", "QR-INV-0004", "Shell Advance 4T AX7 10W-40 (1L)", "Motorcycle Parts", "Shell", 1, 22.00, 35.00, 30.0, 10.0, 25.0, "Rak A-4", "BOTTLE"),
        ("FIL-OIL-PRT", "QR-INV-0005", "Oil Filter Proton Original (X50/Saga/Persona)", "Engine Parts", "Proton", 0, 12.00, 25.00, 35.0, 10.0, 30.0, "Bin B-1", "PCS"),
        ("FIL-OIL-P2", "QR-INV-0006", "Oil Filter Perodua Original (Myvi/Alza/Axia)", "Engine Parts", "Perodua", 0, 10.00, 22.00, 40.0, 10.0, 30.0, "Bin B-2", "PCS"),
        ("FIL-OIL-HND", "QR-INV-0007", "Oil Filter Honda Genuine 15400-RAF-T01", "Engine Parts", "Honda", 0, 18.00, 38.00, 20.0, 6.0, 15.0, "Bin B-3", "PCS"),
        ("FIL-AIR-X50", "QR-INV-0008", "Air Filter Proton X50 OEM", "Engine Parts", "Proton", 0, 28.00, 55.00, 8.0, 4.0, 10.0, "Bin B-4", "PCS"),
        ("BRK-PAD-BRM-F", "QR-INV-0009", "Brembo Ceramic Front Brake Pads (Civic/Vios)", "Brake", "Brembo", 0, 95.00, 160.00, 12.0, 4.0, 10.0, "Rak C-1", "SET"),
        ("BRK-PAD-BDX-F", "QR-INV-0010", "Bendix Metal King Front Brake Pads (Myvi)", "Brake", "Bendix", 0, 65.00, 115.00, 15.0, 5.0, 12.0, "Rak C-2", "SET"),
        ("BRK-FLUID-DOT4", "QR-INV-0011", "Bosch DOT 4 Brake Fluid (500ml)", "Brake", "Bosch", 0, 14.00, 28.00, 22.0, 6.0, 15.0, "Rak C-3", "BOTTLE"),
        ("SPK-PLG-IRID", "QR-INV-0012", "NGK Laser Iridium Spark Plug ILZKR7B11", "Engine Parts", "NGK", 0, 28.00, 50.00, 24.0, 8.0, 20.0, "Bin D-1", "PCS"),
        ("SPK-PLG-MOTO", "QR-INV-0013", "NGK CPR8EA-9 Spark Plug (Y15ZR/RS150R)", "Motorcycle Parts", "NGK", 4, 8.50, 18.00, 45.0, 12.0, 30.0, "Bin D-2", "PCS"),
        ("CHN-SPK-Y15", "QR-INV-0014", "DID 428HD Sprocket & O-Ring Chain Set Y15ZR", "Motorcycle Parts", "DID", 4, 85.00, 145.00, 8.0, 3.0, 8.0, "Rak E-1", "SET"),
        ("CHN-SPK-RS150", "QR-INV-0015", "RK Takasago Chain & Sprocket Set RS150R", "Motorcycle Parts", "RK", 4, 88.00, 150.00, 6.0, 3.0, 8.0, "Rak E-2", "SET"),
        ("TYR-MICH-MOTO", "QR-INV-0016", "Michelin Pilot Street 2 (80/90-17)", "Motorcycle Parts", "Michelin", 3, 75.00, 115.00, 10.0, 4.0, 10.0, "Rak T-1", "PCS"),
        ("TYR-CONT-CC6", "QR-INV-0017", "Continental ComfortContact CC6 195/55R15", "Tyres", "Continental", 3, 140.00, 210.00, 8.0, 4.0, 8.0, "Rak T-2", "PCS"),
        ("BAT-AMR-NS60", "QR-INV-0018", "Amaron Hi-Life NS60L Maintenance Free", "Electrical", "Amaron", 3, 175.00, 260.00, 6.0, 3.0, 6.0, "Rak BAT-1", "PCS"),
        ("BAT-KOYO-5AH", "QR-INV-0019", "Koyo MF Gel Battery YTZ5S (Motorcycle)", "Motorcycle Parts", "Koyo", 3, 42.00, 75.00, 12.0, 4.0, 10.0, "Rak BAT-2", "PCS"),
        ("CLNT-TOY-RED", "QR-INV-0020", "Toyota Super Long Life Coolant 50/50 (4L)", "Consumables", "Toyota", 1, 55.00, 95.00, 9.0, 4.0, 8.0, "Rak A-5", "BOTTLE"),
        # Paint & Body repair materials
        ("PNT-PRM-2K", "QR-INV-0021", "Nippon Paint 2K Primer Surfacer (1L)", "Primer", "Nippon", 2, 45.00, 75.00, 12.0, 4.0, 10.0, "Rak P-1", "LITER"),
        ("PNT-CLR-GLAS", "QR-INV-0022", "Glasurit High Gloss Clear Coat 2:1 (1L + Hardener)", "Clear Coat", "Glasurit", 2, 85.00, 140.00, 10.0, 4.0, 8.0, "Rak P-2", "SET"),
        ("PNT-PUT-POLY", "QR-INV-0023", "Polyester Body Filler / Putty 3kg + Hardener", "Body Repair Materials", "Evercoat", 2, 38.00, 65.00, 14.0, 5.0, 10.0, "Rak P-3", "TIN"),
        ("PNT-THN-2K", "QR-INV-0024", "Slow Drying 2K Thinner High Grade (5L)", "Consumables", "Nippon", 2, 48.00, 80.00, 11.0, 4.0, 8.0, "Rak P-4", "TIN"),
        ("SND-PAP-P800", "QR-INV-0025", "3M Wetordry Sandpaper P800", "Sandpaper", "3M", 2, 1.20, 2.50, 80.0, 25.0, 50.0, "Kotak S-1", "PCS"),
        ("SND-PAP-P1500", "QR-INV-0026", "3M Wetordry Sandpaper P1500", "Sandpaper", "3M", 2, 1.30, 2.80, 75.0, 25.0, 50.0, "Kotak S-2", "PCS"),
        ("MSK-TAP-24", "QR-INV-0027", "Automotive Masking Tape 24mm x 50m Heat Proof", "Consumables", "3M", 2, 3.50, 7.00, 45.0, 15.0, 30.0, "Kotak M-1", "ROLL"),
        ("POL-CMP-3M", "QR-INV-0028", "3M Fast Cut Plus Rubbing Compound (1L)", "Paint", "3M", 2, 75.00, 125.00, 7.0, 3.0, 6.0, "Rak P-5", "BOTTLE"),
        # Low Stock test items
        ("WPR-SIL-24", "QR-INV-0029", "Silicone Wiper Blade 24-inch Universal", "Consumables", "Bosch", 0, 16.00, 35.00, 2.0, 5.0, 10.0, "Rak W-1", "PCS"), # Low stock!
        ("BLB-H4-HAL", "QR-INV-0030", "Osram H4 Night Breaker 12V 60/55W Headlight", "Electrical", "Osram", 0, 22.00, 45.00, 1.0, 4.0, 8.0, "Bin E-3", "PCS")   # Low stock!
    ]
    inventory_map = {}
    for item in items_data:
        supp_id = supplier_ids[item[5]]
        cursor.execute("""
            INSERT INTO inventory (sku, qr_id, name, category, brand, supplier_id, cost_price, selling_price, stock_qty, min_stock, reorder_qty, location, unit, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1);
        """, (item[0], item[1], item[2], item[3], item[4], supp_id, item[6], item[7], item[8], item[9], item[10], item[11], item[12]))
        inv_id = cursor.lastrowid
        inventory_map[item[0]] = {
            "id": inv_id,
            "sku": item[0],
            "name": item[2],
            "price": item[7],
            "cost": item[6],
            "stock": item[8]
        }
        # Record initial stock in Stock Ledger
        cursor.execute("""
            INSERT INTO stock_movements (inventory_id, qty, movement_type, before_qty, after_qty, user_id, reference_type, reference_id, reason, is_demo)
            VALUES (?, ?, 'IN', 0.0, ?, ?, 'MANUAL', 'STK-INIT', 'Baki Permulaan Stok Bengkel GM GEAR ARAU', 1);
        """, (inv_id, item[8], item[8], admin_id))

    # 7. Sample Quotations
    # Auto Service Quotation
    cursor.execute("""
        INSERT INTO quotations (quote_no, customer_id, vehicle_id, service_type, subtotal, discount, tax, total, validity_date, status, notes, created_by, is_demo)
        VALUES ('QUO-2026-000001', ?, ?, 'AUTO_SERVICE', 328.00, 18.00, 0.0, 310.00, '2026-10-15', 'SENT', 'Sebut harga servis berkala dan penukaran pad brek Proton X50.', ?, 1);
    """, (customer_ids[0], car_ids[0], admin_id))
    q1_id = cursor.lastrowid
    cursor.execute("INSERT INTO quotation_lines (quotation_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'OIL-SYN-5W40', 'Petronas Syntium 3000 5W-40 (4L)', 1, 168.0, 168.0);", (q1_id, inventory_map["OIL-SYN-5W40"]["id"]))
    cursor.execute("INSERT INTO quotation_lines (quotation_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'FIL-OIL-PRT', 'Oil Filter Proton Original', 1, 25.0, 25.0);", (q1_id, inventory_map["FIL-OIL-PRT"]["id"]))
    cursor.execute("INSERT INTO quotation_lines (quotation_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Servis & Pemeriksaan Brek 24 Poin', 1, 60.0, 60.0);", (q1_id,))
    cursor.execute("INSERT INTO quotation_lines (quotation_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'BRK-FLUID-DOT4', 'Bosch DOT 4 Brake Fluid', 1, 28.0, 28.0);", (q1_id, inventory_map["BRK-FLUID-DOT4"]["id"]))

    # Body & Paint Quotation
    cursor.execute("""
        INSERT INTO quotations (quote_no, customer_id, vehicle_id, service_type, subtotal, discount, tax, total, validity_date, status, notes, created_by, is_demo)
        VALUES ('QUO-2026-000002', ?, ?, 'BODY_PAINT', 850.00, 50.00, 0.0, 800.00, '2026-10-20', 'ACCEPTED', 'Ketuk & Cat Semula Front Bumper & Fender Kiri Perodua Myvi.', ?, 1);
    """, (customer_ids[1], car_ids[1], admin_id))
    q2_id = cursor.lastrowid
    cursor.execute("INSERT INTO quotation_lines (quotation_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'MATERIAL', ?, 'PNT-CLR-GLAS', 'Glasurit Clear Coat & 2K Primer Set', 1, 215.0, 215.0);", (q2_id, inventory_map["PNT-CLR-GLAS"]["id"]))
    cursor.execute("INSERT INTO quotation_lines (quotation_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Mengetuk Panel & Simen Halus', 1, 285.0, 285.0);", (q2_id,))
    cursor.execute("INSERT INTO quotation_lines (quotation_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Semburan Cat Oven & Polishing QC', 1, 350.0, 350.0);", (q2_id,))

    # 8. Work Orders / Jobs for all 3 categories
    # Job 1: AUTO SERVICE
    cursor.execute("""
        INSERT INTO jobs (job_no, service_type, customer_id, vehicle_id, mileage, complaint, inspection, diagnosis, recommendation, technician_id, status, estimated_completion, parts_total, materials_total, labour_total, discount, estimated_total, notes, created_by, is_demo)
        VALUES ('JOB-2026-000001', 'AUTO_SERVICE', ?, ?, 42500, 'Enjin berbunyi kasar semasa idle, servis 40k km overdue', 'Minyak enjin hitam legam, pad brek depan tinggal 30%', 'Minyak enjin tamat tempoh, pad brek haus', 'Tukar minyak full synthetic, filter, dan pad brek', ?, 'IN_PROGRESS', '2026-09-26 17:00:00', 328.00, 0.0, 70.00, 0.0, 398.00, 'Pelanggan minta siap petang ini', ?, 1);
    """, (customer_ids[0], car_ids[0], mechanic_id, admin_id))
    job1_id = cursor.lastrowid
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'PART', ?, 'OIL-SYN-5W40', 'Petronas Syntium 3000 5W-40 (4L)', 1, 168.0, 168.0);", (job1_id, inventory_map["OIL-SYN-5W40"]["id"]))
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'PART', ?, 'FIL-OIL-PRT', 'Oil Filter Proton Original', 1, 25.0, 25.0);", (job1_id, inventory_map["FIL-OIL-PRT"]["id"]))
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'PART', ?, 'BRK-PAD-BDX-F', 'Bendix Metal King Front Brake Pads', 1, 115.0, 115.0);", (job1_id, inventory_map["BRK-PAD-BDX-F"]["id"]))
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Servis & Pemasangan Brek', 1, 70.0, 70.0);", (job1_id,))

    # Job 2: BODY & PAINT
    damaged_panels_json = json.dumps(["Front Bumper", "Bonnet", "Fender Kiri (FL)"])
    damage_types_json = json.dumps(["Kemek", "Calar Dalam", "Cat Terkupas"])
    cursor.execute("""
        INSERT INTO jobs (job_no, service_type, customer_id, vehicle_id, mileage, complaint, inspection, diagnosis, recommendation, technician_id, status, estimated_completion, parts_total, materials_total, labour_total, discount, estimated_total, notes, damage_description, repair_method, paint_colour, paint_code, damaged_panels, damage_types, paint_quantity, estimated_days, created_by, is_demo)
        VALUES ('JOB-2026-000002', 'BODY_PAINT', ?, ?, 58300, 'Langgar tiang tempat letak kereta, bumper depan pecah sikit dan calar kemek di bonnet', 'Kerosakan panel bahagian depan dan sisi kiri', 'Perlu diketuk, simen putty, primer 2K, sembur cat silver 2K & clear coat 2 lapis', 'Full repair & repaint front section', ?, 'PAINTING', '2026-09-28 18:00:00', 0.0, 280.00, 620.00, 50.00, 850.00, 'Warna Silver S28 matching kilang', 'Kemek 15cm pada bonet dan calar tajam di bumper', 'Mengetuk, Sanding, Putty, Primer 2K, Base Coat, Clear Coat Oven', 'Glittering Silver', 'S28', ?, ?, 1.5, 3, ?, 1);
    """, (customer_ids[1], car_ids[1], mechanic_id, damaged_panels_json, damage_types_json, admin_id))
    job2_id = cursor.lastrowid
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'MATERIAL', ?, 'PNT-PRM-2K', 'Nippon Paint 2K Primer Surfacer (1L)', 1, 75.0, 75.0);", (job2_id, inventory_map["PNT-PRM-2K"]["id"]))
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'MATERIAL', ?, 'PNT-CLR-GLAS', 'Glasurit Clear Coat 2:1 Set', 1, 140.0, 140.0);", (job2_id, inventory_map["PNT-CLR-GLAS"]["id"]))
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'MATERIAL', ?, 'PNT-PUT-POLY', 'Polyester Body Filler 3kg', 1, 65.0, 65.0);", (job2_id, inventory_map["PNT-PUT-POLY"]["id"]))
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Mengetuk & Simen Panel Rosak', 1, 280.0, 280.0);", (job2_id,))
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Cat Oven & Polishing 3M', 1, 340.0, 340.0);", (job2_id,))

    # Job 3: MOTORCYCLE SERVICE
    cursor.execute("""
        INSERT INTO jobs (job_no, service_type, customer_id, vehicle_id, mileage, complaint, inspection, diagnosis, recommendation, technician_id, status, estimated_completion, parts_total, materials_total, labour_total, discount, estimated_total, notes, created_by, is_demo)
        VALUES ('JOB-2026-000003', 'MOTORCYCLE', ?, ?, 28500, 'Rantai motor berbunyi kuat dan longgar, minta tukar minyak 4T', 'Rantai kendur melepasi limit, sprocket tajam, minyak hitam berkeladak', 'Sprocket & rantai haus, perlu tukar set baru dan servis minyak 4T fully synthetic', 'Tukar set DID 428HD & Motul 7100', ?, 'COMPLETED', '2026-09-25 12:00:00', 238.00, 0.0, 30.00, 8.00, 260.00, 'Motor kegunaan harian ulang-alik kerja', ?, 1);
    """, (customer_ids[8], bike_ids[0], mechanic_id, admin_id))
    job3_id = cursor.lastrowid
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'PART', ?, 'OIL-MOTUL-7100', 'Motul 7100 4T 10W-40 (1L)', 1, 75.0, 75.0);", (job3_id, inventory_map["OIL-MOTUL-7100"]["id"]))
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'PART', ?, 'CHN-SPK-Y15', 'DID 428HD Sprocket & O-Ring Chain Set', 1, 145.0, 145.0);", (job3_id, inventory_map["CHN-SPK-Y15"]["id"]))
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'PART', ?, 'SPK-PLG-MOTO', 'NGK CPR8EA-9 Spark Plug', 1, 18.0, 18.0);", (job3_id, inventory_map["SPK-PLG-MOTO"]["id"]))
    cursor.execute("INSERT INTO job_items (job_id, item_type, inventory_id, sku, name, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Pasang Rantai, Sprocket & Servis Enjin', 1, 30.0, 30.0);", (job3_id,))

    # 9. Invoices across different statuses
    # Invoice 1: PAID (Motorcycle Job 3)
    inv1_qr = generate_qr_token()
    cursor.execute("""
        INSERT INTO invoices (invoice_no, job_id, customer_id, vehicle_id, service_type, subtotal, discount, tax, grand_total, deposit_amount, paid_amount, balance_due, status, qr_token, notes, approved_at, approved_by, created_by, is_demo)
        VALUES ('INV-2026-000001', ?, ?, ?, 'MOTORCYCLE', 268.00, 8.00, 0.0, 260.00, 0.0, 260.00, 0.00, 'PAID', ?, 'Telah dibayar penuh via DuitNow QR.', CURRENT_TIMESTAMP, ?, ?, 1);
    """, (job3_id, customer_ids[8], bike_ids[0], inv1_qr, admin_id, admin_id))
    inv1_id = cursor.lastrowid
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'OIL-MOTUL-7100', 'Motul 7100 4T 10W-40 (1L)', 1, 75.0, 75.0);", (inv1_id, inventory_map["OIL-MOTUL-7100"]["id"]))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'CHN-SPK-Y15', 'DID 428HD Sprocket & O-Ring Chain Set', 1, 145.0, 145.0);", (inv1_id, inventory_map["CHN-SPK-Y15"]["id"]))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'SPK-PLG-MOTO', 'NGK CPR8EA-9 Spark Plug', 1, 18.0, 18.0);", (inv1_id, inventory_map["SPK-PLG-MOTO"]["id"]))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Pasang Rantai, Sprocket & Servis Enjin', 1, 30.0, 30.0);", (inv1_id,))

    # Receipt for Invoice 1
    cursor.execute("""
        INSERT INTO payments (receipt_no, invoice_id, amount, payment_method, payment_type, reference_no, notes, created_by, is_demo)
        VALUES ('RCP-2026-000001', ?, 260.00, 'DUITNOW_QR', 'FINAL', 'DN-998811223', 'Bayaran penuh imbasan DuitNow QR kaunter', ?, 1);
    """, (inv1_id, cashier_id))
    pay1_id = cursor.lastrowid
    rcp_snapshot_1 = {
        "receipt_no": "RCP-2026-000001",
        "invoice_no": "INV-2026-000001",
        "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "customer_name": "Azman bin Ibrahim",
        "customer_phone": "019-3322114",
        "vehicle_reg": "RAP 8819",
        "vehicle_model": "Yamaha Y15ZR",
        "service_type": "MOTORCYCLE",
        "grand_total": 260.00,
        "previous_paid": 0.0,
        "payment_amount": 260.00,
        "total_paid": 260.00,
        "balance_due": 0.00,
        "payment_method": "DUITNOW_QR",
        "payment_type": "FINAL",
        "cashier_name": "Siti Juruwang",
        "items": [
            {"sku": "OIL-MOTUL-7100", "description": "Motul 7100 4T 10W-40 (1L)", "qty": 1, "unit_price": 75.0, "amount": 75.0},
            {"sku": "CHN-SPK-Y15", "description": "DID 428HD Sprocket & O-Ring Chain Set", "qty": 1, "unit_price": 145.0, "amount": 145.0},
            {"sku": "SPK-PLG-MOTO", "description": "NGK CPR8EA-9 Spark Plug", "qty": 1, "unit_price": 18.0, "amount": 18.0},
            {"sku": "-", "description": "Upah Pasang Rantai, Sprocket & Servis Enjin", "qty": 1, "unit_price": 30.0, "amount": 30.0}
        ]
    }
    cursor.execute("""
        INSERT INTO receipts (receipt_no, payment_id, invoice_id, receipt_type, data_snapshot, is_demo)
        VALUES ('RCP-2026-000001', ?, ?, 'FINAL', ?, 1);
    """, (pay1_id, inv1_id, json.dumps(rcp_snapshot_1, ensure_ascii=False)))

    # Invoice 2: PARTIALLY_PAID with Deposit (Body & Paint Job 2)
    inv2_qr = generate_qr_token()
    cursor.execute("""
        INSERT INTO invoices (invoice_no, job_id, customer_id, vehicle_id, service_type, subtotal, discount, tax, grand_total, deposit_amount, paid_amount, balance_due, status, qr_token, notes, approved_at, approved_by, created_by, is_demo)
        VALUES ('INV-2026-000002', ?, ?, ?, 'BODY_PAINT', 900.00, 50.00, 0.0, 850.00, 300.00, 300.00, 550.00, 'PARTIALLY_PAID', ?, 'Deposit cat RM300 telah diterima.', CURRENT_TIMESTAMP, ?, ?, 1);
    """, (job2_id, customer_ids[1], car_ids[1], inv2_qr, admin_id, admin_id))
    inv2_id = cursor.lastrowid
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'MATERIAL', ?, 'PNT-PRM-2K', 'Nippon Paint 2K Primer Surfacer (1L)', 1, 75.0, 75.0);", (inv2_id, inventory_map["PNT-PRM-2K"]["id"]))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'MATERIAL', ?, 'PNT-CLR-GLAS', 'Glasurit Clear Coat 2:1 Set', 1, 140.0, 140.0);", (inv2_id, inventory_map["PNT-CLR-GLAS"]["id"]))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'MATERIAL', ?, 'PNT-PUT-POLY', 'Polyester Body Filler 3kg', 1, 65.0, 65.0);", (inv2_id, inventory_map["PNT-PUT-POLY"]["id"]))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Mengetuk & Simen Panel Rosak', 1, 280.0, 280.0);", (inv2_id,))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Cat Oven & Polishing 3M', 1, 340.0, 340.0);", (inv2_id,))

    # Deposit payment & receipt for Invoice 2
    cursor.execute("""
        INSERT INTO payments (receipt_no, invoice_id, amount, payment_method, payment_type, reference_no, notes, created_by, is_demo)
        VALUES ('RCP-2026-000002', ?, 300.00, 'BANK_TRANSFER', 'DEPOSIT', 'MAYBANK-882190', 'Deposit kerja mengecat & mengetuk', ?, 1);
    """, (inv2_id, cashier_id))
    pay2_id = cursor.lastrowid
    rcp_snapshot_2 = {
        "receipt_no": "RCP-2026-000002",
        "invoice_no": "INV-2026-000002",
        "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "customer_name": "Tan Wei Ming",
        "customer_phone": "016-4321987",
        "vehicle_reg": "KV 5678",
        "vehicle_model": "Perodua Myvi 1.5 H",
        "service_type": "BODY_PAINT",
        "grand_total": 850.00,
        "previous_paid": 0.0,
        "payment_amount": 300.00,
        "total_paid": 300.00,
        "balance_due": 550.00,
        "payment_method": "BANK_TRANSFER",
        "payment_type": "DEPOSIT",
        "cashier_name": "Siti Juruwang",
        "items": [
            {"sku": "PNT-PRM-2K", "description": "Nippon Paint 2K Primer Surfacer (1L)", "qty": 1, "unit_price": 75.0, "amount": 75.0},
            {"sku": "PNT-CLR-GLAS", "description": "Glasurit Clear Coat 2:1 Set", "qty": 1, "unit_price": 140.0, "amount": 140.0},
            {"sku": "PNT-PUT-POLY", "description": "Polyester Body Filler 3kg", "qty": 1, "unit_price": 65.0, "amount": 65.0},
            {"sku": "-", "description": "Upah Mengetuk & Simen Panel Rosak", "qty": 1, "unit_price": 280.0, "amount": 280.0},
            {"sku": "-", "description": "Upah Cat Oven & Polishing 3M", "qty": 1, "unit_price": 340.0, "amount": 340.0}
        ]
    }
    cursor.execute("""
        INSERT INTO receipts (receipt_no, payment_id, invoice_id, receipt_type, data_snapshot, is_demo)
        VALUES ('RCP-2026-000002', ?, ?, 'DEPOSIT', ?, 1);
    """, (pay2_id, inv2_id, json.dumps(rcp_snapshot_2, ensure_ascii=False)))

    # Invoice 3: APPROVED (Auto Service Job 1) - Stock deducted, awaiting payment
    inv3_qr = generate_qr_token()
    cursor.execute("""
        INSERT INTO invoices (invoice_no, job_id, customer_id, vehicle_id, service_type, subtotal, discount, tax, grand_total, deposit_amount, paid_amount, balance_due, status, qr_token, notes, approved_at, approved_by, created_by, is_demo)
        VALUES ('INV-2026-000003', ?, ?, ?, 'AUTO_SERVICE', 378.00, 0.0, 0.0, 378.00, 0.0, 0.0, 378.00, 'APPROVED', ?, 'Servis siap, menunggu pengambilan kenderaan oleh pemilik.', CURRENT_TIMESTAMP, ?, ?, 1);
    """, (job1_id, customer_ids[0], car_ids[0], inv3_qr, admin_id, admin_id))
    inv3_id = cursor.lastrowid
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'OIL-SYN-5W40', 'Petronas Syntium 3000 5W-40 (4L)', 1, 168.0, 168.0);", (inv3_id, inventory_map["OIL-SYN-5W40"]["id"]))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'FIL-OIL-PRT', 'Oil Filter Proton Original', 1, 25.0, 25.0);", (inv3_id, inventory_map["FIL-OIL-PRT"]["id"]))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'BRK-PAD-BDX-F', 'Bendix Metal King Front Brake Pads', 1, 115.0, 115.0);", (inv3_id, inventory_map["BRK-PAD-BDX-F"]["id"]))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Servis & Pemasangan Brek', 1, 70.0, 70.0);", (inv3_id,))

    # Invoice 4: DRAFT (Pending approval, stock not deducted)
    inv4_qr = generate_qr_token()
    cursor.execute("""
        INSERT INTO invoices (invoice_no, job_id, customer_id, vehicle_id, service_type, subtotal, discount, tax, grand_total, deposit_amount, paid_amount, balance_due, status, qr_token, notes, created_by, is_demo)
        VALUES ('INV-2026-000004', NULL, ?, ?, 'AUTO_SERVICE', 288.00, 20.00, 0.0, 268.00, 0.0, 0.0, 268.00, 'DRAFT', ?, 'Draf invois tukar bateri Amaron Honda Civic.', ?, 1);
    """, (customer_ids[2], car_ids[2], inv4_qr, cashier_id))
    inv4_id = cursor.lastrowid
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'BAT-AMR-NS60', 'Amaron Hi-Life NS60L Maintenance Free', 1, 260.0, 260.0);", (inv4_id, inventory_map["BAT-AMR-NS60"]["id"]))
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'LABOUR', NULL, NULL, 'Upah Pemasangan & Ujian Alternator', 1, 28.0, 28.0);", (inv4_id,))

    # Invoice 5: CANCELLED
    inv5_qr = generate_qr_token()
    cursor.execute("""
        INSERT INTO invoices (invoice_no, job_id, customer_id, vehicle_id, service_type, subtotal, discount, tax, grand_total, deposit_amount, paid_amount, balance_due, status, qr_token, notes, cancelled_at, cancelled_by, cancel_reason, created_by, is_demo)
        VALUES ('INV-2026-000005', NULL, ?, ?, 'MOTORCYCLE', 115.00, 0.0, 0.0, 115.00, 0.0, 0.0, 115.00, 'CANCELLED', ?, 'Pelanggan batalkan pesanan tayar', CURRENT_TIMESTAMP, ?, 'Pelanggan minta ganti saiz lain di bengkel lain', ?, 1);
    """, (customer_ids[9], bike_ids[1], inv5_qr, admin_id, admin_id))
    inv5_id = cursor.lastrowid
    cursor.execute("INSERT INTO invoice_lines (invoice_id, item_type, inventory_id, sku, description, qty, unit_price, amount) VALUES (?, 'PART', ?, 'TYR-MICH-MOTO', 'Michelin Pilot Street 2 (80/90-17)', 1, 115.0, 115.0);", (inv5_id, inventory_map["TYR-MICH-MOTO"]["id"]))

    # 10. Service Reminders
    cursor.execute("""
        INSERT INTO service_reminders (customer_id, vehicle_id, service_type, last_service_date, next_service_date, next_mileage, status, notes)
        VALUES (?, ?, 'AUTO_SERVICE', '2026-07-20', '2026-10-20', 47500, 'PENDING', 'Peringatan servis 5,000km Proton X50');
    """, (customer_ids[0], car_ids[0]))
    cursor.execute("""
        INSERT INTO service_reminders (customer_id, vehicle_id, service_type, last_service_date, next_service_date, next_mileage, status, notes)
        VALUES (?, ?, 'MOTORCYCLE', '2026-08-10', '2026-10-10', 31500, 'PENDING', 'Peringatan tukar minyak 4T Yamaha Y15ZR');
    """, (customer_ids[8], bike_ids[0]))

    # 11. Initial Audit Logs
    audit_samples = [
        (admin_id, "Pengurus Utama (Admin)", "ADMIN", "LOGIN_SUCCESS", "AUTH", "AUTH-001", None, {"ip": "127.0.0.1", "action": "Log masuk pentadbir"}),
        (admin_id, "Pengurus Utama (Admin)", "ADMIN", "SYSTEM_INIT", "SETTINGS", "CONFIG-1", None, {"company": "GM GEAR ARAU", "status": "Inisialisasi sistem berjaya"}),
        (admin_id, "Pengurus Utama (Admin)", "ADMIN", "INVOICE_APPROVED", "INVOICE", str(inv3_id), {"status": "DRAFT"}, {"status": "APPROVED", "invoice_no": "INV-2026-000003"}),
        (cashier_id, "Siti Juruwang", "CASHIER", "PAYMENT_RECEIVED", "PAYMENT", "RCP-2026-000001", {"balance": 260.0}, {"amount": 260.0, "method": "DUITNOW_QR", "status": "PAID"}),
        (cashier_id, "Siti Juruwang", "CASHIER", "PAYMENT_RECEIVED", "PAYMENT", "RCP-2026-000002", {"balance": 850.0}, {"amount": 300.0, "method": "BANK_TRANSFER", "type": "DEPOSIT"})
    ]
    for a in audit_samples:
        cursor.execute("""
            INSERT INTO audit_logs (user_id, user_name, role, action, module, record_id, prev_value, new_value, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, '127.0.0.1');
        """, (a[0], a[1], a[2], a[3], a[4], a[5], json.dumps(a[6]) if a[6] else None, json.dumps(a[7]) if a[7] else None))

    conn.commit()
    conn.close()
    print("Penjanaan Data Demo GM GEAR ARAU selesai dengan jaya!")

if __name__ == "__main__":
    seed_database()
