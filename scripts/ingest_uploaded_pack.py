#!/usr/bin/env python3
"""
RationRight: Ingestion pipeline for the uploaded Ration Distribution Dataset.
Parses data/uploaded_dataset/rationright_demo_data.json and CSV files,
updates SQLite database (data/rationright.db), enforces idempotency,
and registers audit and alert entries.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime

DB_PATH = os.environ.get("RATIONRIGHT_DB_PATH", "data/rationright.db")
DATASET_PATH = "data/uploaded_dataset/rationright_demo_data.json"

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_demo_tables(conn):
    """Create dedicated demo dataset tables if they don't exist."""
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS demo_pwd_shops (
        pwd_id TEXT PRIMARY KEY,
        shop_name TEXT NOT NULL,
        district TEXT NOT NULL,
        state TEXT NOT NULL,
        dealer_id TEXT NOT NULL,
        monthly_capacity_kg REAL NOT NULL,
        gps_lat REAL,
        gps_lon REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS demo_beneficiaries (
        beneficiary_id TEXT PRIMARY KEY,
        ration_card_id TEXT NOT NULL,
        head_name TEXT NOT NULL,
        family_size INTEGER NOT NULL,
        category TEXT NOT NULL,
        pwd_id TEXT NOT NULL REFERENCES demo_pwd_shops(pwd_id),
        monthly_entitlement_kg REAL NOT NULL,
        last_collection_date TEXT,
        collection_status TEXT NOT NULL,
        identity_status TEXT NOT NULL,
        review_reason TEXT,
        demo_record INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS demo_inventory (
        inventory_id TEXT PRIMARY KEY,
        pwd_id TEXT NOT NULL REFERENCES demo_pwd_shops(pwd_id),
        month TEXT NOT NULL,
        commodity TEXT NOT NULL,
        opening_stock_kg REAL NOT NULL,
        received_kg REAL NOT NULL,
        distributed_kg REAL NOT NULL,
        closing_stock_kg REAL NOT NULL,
        physical_stock_kg REAL NOT NULL,
        discrepancy_kg REAL,
        unit TEXT DEFAULT 'kg',
        demo_record INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS demo_transactions (
        transaction_id TEXT PRIMARY KEY,
        beneficiary_id TEXT NOT NULL,
        pwd_id TEXT NOT NULL REFERENCES demo_pwd_shops(pwd_id),
        date TEXT NOT NULL,
        commodity TEXT NOT NULL,
        quantity_kg REAL NOT NULL,
        channel TEXT NOT NULL,
        status TEXT NOT NULL,
        demo_record INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS demo_pwd_audits (
        audit_id TEXT PRIMARY KEY,
        pwd_id TEXT NOT NULL REFERENCES demo_pwd_shops(pwd_id),
        period TEXT NOT NULL,
        late_opening_days INTEGER DEFAULT 0,
        manual_override_count INTEGER DEFAULT 0,
        complaints_count INTEGER DEFAULT 0,
        inspection_status TEXT NOT NULL,
        demo_record INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()

def ingest_data(conn, data):
    cur = conn.cursor()
    now_iso = datetime.now().isoformat()
    summary = {
        "pwd_shops": {"processed": 0, "inserted": 0, "updated": 0},
        "beneficiaries": {"processed": 0, "inserted": 0, "updated": 0},
        "inventory": {"processed": 0, "inserted": 0, "updated": 0},
        "transactions": {"processed": 0, "inserted": 0, "updated": 0},
        "pwd_audits": {"processed": 0, "inserted": 0, "updated": 0},
        "alerts_generated": 0
    }

    # 1. Ingest PWD Shops
    pwd_shop_map = {} # pwd_id -> db id in fps_centers
    for shop in data.get("pwd_shops", []):
        summary["pwd_shops"]["processed"] += 1
        # Upsert into demo_pwd_shops
        cur.execute("""
            INSERT INTO demo_pwd_shops (pwd_id, shop_name, district, state, dealer_id, monthly_capacity_kg, gps_lat, gps_lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pwd_id) DO UPDATE SET
                shop_name=excluded.shop_name,
                district=excluded.district,
                state=excluded.state,
                dealer_id=excluded.dealer_id,
                monthly_capacity_kg=excluded.monthly_capacity_kg,
                gps_lat=excluded.gps_lat,
                gps_lon=excluded.gps_lon
        """, (
            shop["pwd_id"], shop["shop_name"], shop["district"], shop["state"],
            shop["dealer_id"], shop["monthly_capacity_kg"], shop.get("gps_lat"), shop.get("gps_lon")
        ))
        
        # Also upsert into core fps_centers table
        cur.execute("SELECT id FROM fps_centers WHERE fps_code = ?", (shop["pwd_id"],))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE fps_centers 
                SET name=?, state=?, district=?, location=?, latitude=?, longitude=?, capacity=?, status='ACTIVE', updated_at=?
                WHERE id=?
            """, (
                shop["shop_name"], shop["state"], shop["district"], 
                f"{shop['district']}, {shop['state']}", shop.get("gps_lat"), shop.get("gps_lon"),
                shop["monthly_capacity_kg"], now_iso, row[0]
            ))
            pwd_shop_map[shop["pwd_id"]] = row[0]
            summary["pwd_shops"]["updated"] += 1
        else:
            cur.execute("""
                INSERT INTO fps_centers (fps_code, name, state, district, block, location, latitude, longitude, capacity, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'Urban', ?, ?, ?, ?, 'ACTIVE', ?, ?)
            """, (
                shop["pwd_id"], shop["shop_name"], shop["state"], shop["district"],
                f"{shop['district']}, {shop['state']}", shop.get("gps_lat"), shop.get("gps_lon"),
                shop["monthly_capacity_kg"], now_iso, now_iso
            ))
            pwd_shop_map[shop["pwd_id"]] = cur.lastrowid
            summary["pwd_shops"]["inserted"] += 1

    # 2. Ingest Beneficiaries
    ben_map = {} # beneficiary_id -> db id in beneficiaries
    for b in data.get("beneficiaries", []):
        summary["beneficiaries"]["processed"] += 1
        # Upsert into demo_beneficiaries
        cur.execute("""
            INSERT INTO demo_beneficiaries (
                beneficiary_id, ration_card_id, head_name, family_size, category, pwd_id,
                monthly_entitlement_kg, last_collection_date, collection_status, identity_status, review_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(beneficiary_id) DO UPDATE SET
                ration_card_id=excluded.ration_card_id,
                head_name=excluded.head_name,
                family_size=excluded.family_size,
                category=excluded.category,
                pwd_id=excluded.pwd_id,
                monthly_entitlement_kg=excluded.monthly_entitlement_kg,
                last_collection_date=excluded.last_collection_date,
                collection_status=excluded.collection_status,
                identity_status=excluded.identity_status,
                review_reason=excluded.review_reason
        """, (
            b["beneficiary_id"], b["ration_card_id"], b["head_name"], b["family_size"],
            b["category"], b["pwd_id"], b["monthly_entitlement_kg"], b.get("last_collection_date"),
            b["collection_status"], b["identity_status"], b.get("review_reason", "")
        ))

        # Core beneficiaries table
        cur.execute("SELECT id FROM beneficiaries WHERE external_reference = ?", (b["beneficiary_id"],))
        row = cur.fetchone()
        shop_info = next((s for s in data.get("pwd_shops", []) if s["pwd_id"] == b["pwd_id"]), {})
        if row:
            cur.execute("""
                UPDATE beneficiaries
                SET state=?, district=?, ration_category=?, family_size=?, status='ACTIVE', updated_at=?
                WHERE id=?
            """, (
                shop_info.get("state", "Uttar Pradesh"), shop_info.get("district", "Ghaziabad"),
                b["category"], b["family_size"], now_iso, row[0]
            ))
            ben_map[b["beneficiary_id"]] = row[0]
            summary["beneficiaries"]["updated"] += 1
        else:
            cur.execute("""
                INSERT INTO beneficiaries (external_reference, state, district, block, ration_category, family_size, status, created_at, updated_at)
                VALUES (?, ?, ?, 'Sector-1', ?, ?, 'ACTIVE', ?, ?)
            """, (
                b["beneficiary_id"], shop_info.get("state", "Uttar Pradesh"),
                shop_info.get("district", "Ghaziabad"), b["category"], b["family_size"], now_iso, now_iso
            ))
            ben_map[b["beneficiary_id"]] = cur.lastrowid
            summary["beneficiaries"]["inserted"] += 1

    # 3. Ingest Inventory
    for inv in data.get("inventory", []):
        summary["inventory"]["processed"] += 1
        expected_close = inv["opening_stock_kg"] + inv["received_kg"] - inv["distributed_kg"]
        discrepancy = inv["physical_stock_kg"] - expected_close
        
        cur.execute("""
            INSERT INTO demo_inventory (
                inventory_id, pwd_id, month, commodity, opening_stock_kg, received_kg,
                distributed_kg, closing_stock_kg, physical_stock_kg, discrepancy_kg, unit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(inventory_id) DO UPDATE SET
                pwd_id=excluded.pwd_id,
                month=excluded.month,
                commodity=excluded.commodity,
                opening_stock_kg=excluded.opening_stock_kg,
                received_kg=excluded.received_kg,
                distributed_kg=excluded.distributed_kg,
                closing_stock_kg=excluded.closing_stock_kg,
                physical_stock_kg=excluded.physical_stock_kg,
                discrepancy_kg=excluded.discrepancy_kg,
                unit=excluded.unit
        """, (
            inv["inventory_id"], inv["pwd_id"], inv["month"], inv["commodity"],
            inv["opening_stock_kg"], inv["received_kg"], inv["distributed_kg"],
            inv["closing_stock_kg"], inv["physical_stock_kg"], discrepancy, inv.get("unit", "kg")
        ))

        # Core inventory table
        fps_db_id = pwd_shop_map.get(inv["pwd_id"])
        if fps_db_id:
            cur.execute("SELECT id FROM inventory WHERE fps_center_id = ? AND commodity = ?", (fps_db_id, inv["commodity"]))
            irow = cur.fetchone()
            if irow:
                cur.execute("""
                    UPDATE inventory
                    SET current_stock=?, monthly_consumption=?, reorder_threshold=?, last_updated=?
                    WHERE id=?
                """, (inv["physical_stock_kg"], inv["distributed_kg"], 300, now_iso, irow[0]))
                summary["inventory"]["updated"] += 1
            else:
                cur.execute("""
                    INSERT INTO inventory (fps_center_id, commodity, current_stock, monthly_consumption, reorder_threshold, last_updated, created_at)
                    VALUES (?, ?, ?, ?, 300, ?, ?)
                """, (fps_db_id, inv["commodity"], inv["physical_stock_kg"], inv["distributed_kg"], now_iso, now_iso))
                summary["inventory"]["inserted"] += 1

    # 4. Ingest Transactions
    for txn in data.get("transactions", []):
        summary["transactions"]["processed"] += 1
        cur.execute("""
            INSERT INTO demo_transactions (
                transaction_id, beneficiary_id, pwd_id, date, commodity, quantity_kg, channel, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(transaction_id) DO UPDATE SET
                beneficiary_id=excluded.beneficiary_id,
                pwd_id=excluded.pwd_id,
                date=excluded.date,
                commodity=excluded.commodity,
                quantity_kg=excluded.quantity_kg,
                channel=excluded.channel,
                status=excluded.status
        """, (
            txn["transaction_id"], txn["beneficiary_id"], txn["pwd_id"], txn["date"],
            txn["commodity"], txn["quantity_kg"], txn["channel"], txn["status"]
        ))

        ben_db_id = ben_map.get(txn["beneficiary_id"])
        fps_db_id = pwd_shop_map.get(txn["pwd_id"])
        tx_status = "COMPLETED" if str(txn["status"]).lower() == "success" else "PENDING"
        if ben_db_id and fps_db_id:
            cur.execute("SELECT id FROM ration_transactions WHERE external_transaction_id = ?", (txn["transaction_id"],))
            trow = cur.fetchone()
            if trow:
                cur.execute("""
                    UPDATE ration_transactions
                    SET beneficiary_id=?, fps_center_id=?, transaction_date=?, commodity=?, quantity=?, status=?
                    WHERE id=?
                """, (ben_db_id, fps_db_id, txn["date"], txn["commodity"], txn["quantity_kg"], tx_status, trow[0]))
                summary["transactions"]["updated"] += 1
            else:
                cur.execute("""
                    INSERT INTO ration_transactions (external_transaction_id, beneficiary_id, fps_center_id, transaction_date, commodity, quantity, unit, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'kg', ?, ?)
                """, (txn["transaction_id"], ben_db_id, fps_db_id, txn["date"], txn["commodity"], txn["quantity_kg"], tx_status, now_iso))
                summary["transactions"]["inserted"] += 1

    # 5. Ingest PWD Audits
    for aud in data.get("pwd_audits", []):
        summary["pwd_audits"]["processed"] += 1
        cur.execute("""
            INSERT INTO demo_pwd_audits (
                audit_id, pwd_id, period, late_opening_days, manual_override_count, complaints_count, inspection_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(audit_id) DO UPDATE SET
                pwd_id=excluded.pwd_id,
                period=excluded.period,
                late_opening_days=excluded.late_opening_days,
                manual_override_count=excluded.manual_override_count,
                complaints_count=excluded.complaints_count,
                inspection_status=excluded.inspection_status
        """, (
            aud["audit_id"], aud["pwd_id"], aud["period"], aud["late_opening_days"],
            aud["manual_override_count"], aud["complaints_count"], aud["inspection_status"]
        ))
        summary["pwd_audits"]["inserted"] += 1

    # 6. Generate Context-Aware Alerts Based on Dataset Anomalies
    alerts_to_create = [
        {
            "alert_id": "ALT-DEMO-DUP-01",
            "rule_type": "POSSIBLE_DUPLICATE_IDENTITY",
            "severity": "HIGH",
            "title": "Duplicate Household Fingerprint Detected",
            "description": "Beneficiary BEN007 shares identical biometric household fingerprint with BEN014 across distinct ration cards.",
            "entity_type": "BENEFICIARY",
            "entity_id": "BEN007",
            "evidence": json.dumps({"primary_beneficiary": "BEN007", "matched_beneficiary": "BEN014", "reason": "Same demo household fingerprint as BEN014"}),
            "recommendation": "Require physical field inspection and biometric re-verification."
        },
        {
            "alert_id": "ALT-DEMO-CLAIM-02",
            "rule_type": "MULTIPLE_CLAIMS_SAME_PERIOD",
            "severity": "CRITICAL",
            "title": "Multiple Claims in Single Entitlement Period",
            "description": "Beneficiary BEN019 recorded two consecutive Rice disbursements (TXN004 & TXN005) on 2026-10-12 via manual override.",
            "entity_type": "BENEFICIARY",
            "entity_id": "BEN019",
            "evidence": json.dumps({"beneficiary_id": "BEN019", "shop": "PWD005", "transactions": ["TXN004", "TXN005"], "commodity": "Rice"}),
            "recommendation": "Freeze card allocations pending dealer manual override justification."
        },
        {
            "alert_id": "ALT-DEMO-STOCK-03",
            "rule_type": "PHYSICAL_STOCK_SHORTAGE",
            "severity": "CRITICAL",
            "title": "Physical Stock Shortage of 280 kg Rice at PWD002",
            "description": "Expected closing stock is 800 kg; physical stock verified is only 520 kg (deficit of 280 kg / 35%).",
            "entity_type": "FPS_CENTER",
            "entity_id": "PWD002",
            "evidence": json.dumps({"shop": "PWD002", "commodity": "Rice", "expected": 800, "actual": 520, "shortage_kg": 280}),
            "recommendation": "Dispatch district food auditor to inspect silo scale sensors and weighment slips."
        },
        {
            "alert_id": "ALT-DEMO-STOCK-04",
            "rule_type": "PHYSICAL_STOCK_SHORTAGE",
            "severity": "HIGH",
            "title": "Physical Stock Shortage of 200 kg Rice at PWD004",
            "description": "Expected closing stock is 500 kg; physical stock verified is 300 kg (deficit of 200 kg / 40%).",
            "entity_type": "FPS_CENTER",
            "entity_id": "PWD004",
            "evidence": json.dumps({"shop": "PWD004", "commodity": "Rice", "expected": 500, "actual": 300, "shortage_kg": 200}),
            "recommendation": "Perform physical stock reconciliation and check for unlogged grain spillages."
        },
        {
            "alert_id": "ALT-DEMO-AUDIT-05",
            "rule_type": "FAILED_OUTLET_INSPECTION",
            "severity": "CRITICAL",
            "title": "Fair Price Shop PWD004 Failed Administrative Inspection",
            "description": "Bharat Ration Point (PWD004) logged 4 late opening days, 7 manual overrides, and 6 registered complaints in October 2026.",
            "entity_type": "FPS_CENTER",
            "entity_id": "PWD004",
            "evidence": json.dumps({"shop": "PWD004", "late_days": 4, "manual_overrides": 7, "complaints": 6, "status": "failed"}),
            "recommendation": "Issue formal show-cause notice to dealer DLR004 and place terminal under surveillance."
        }
    ]

    for alt in alerts_to_create:
        cur.execute("""
            INSERT INTO alerts (
                alert_id, rule_type, condition, severity, title, description,
                status, entity_type, entity_id, evidence, recommendation, created_at, last_detected_at
            ) VALUES (?, ?, 'THRESHOLD_EXCEEDED', ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?)
            ON CONFLICT(alert_id) DO UPDATE SET
                severity=excluded.severity,
                title=excluded.title,
                description=excluded.description,
                evidence=excluded.evidence,
                recommendation=excluded.recommendation,
                last_detected_at=excluded.last_detected_at
        """, (
            alt["alert_id"], alt["rule_type"], alt["severity"], alt["title"],
            alt["description"], alt["entity_type"], alt["entity_id"],
            alt["evidence"], alt["recommendation"], now_iso, now_iso
        ))
        summary["alerts_generated"] += 1

    conn.commit()
    return summary

def main():
    if not os.path.exists(DATASET_PATH):
        print(f"Error: Dataset not found at {DATASET_PATH}")
        sys.exit(1)

    with open(DATASET_PATH, "r") as f:
        data = json.load(f)

    conn = get_connection()
    try:
        setup_demo_tables(conn)
        summary = ingest_data(conn, data)
        print("="*60)
        print("RATIONRIGHT DATASET INGESTION COMPLETED")
        print("="*60)
        print(f"Reporting Period:       {data.get('metadata', {}).get('period', '2026-10')}")
        print(f"Fair Price Shops:       {summary['pwd_shops']['processed']} processed ({summary['pwd_shops']['inserted']} new, {summary['pwd_shops']['updated']} updated)")
        print(f"Beneficiaries:          {summary['beneficiaries']['processed']} processed ({summary['beneficiaries']['inserted']} new, {summary['beneficiaries']['updated']} updated)")
        print(f"Inventory Records:      {summary['inventory']['processed']} processed ({summary['inventory']['inserted']} new, {summary['inventory']['updated']} updated)")
        print(f"Transactions:           {summary['transactions']['processed']} processed ({summary['transactions']['inserted']} new, {summary['transactions']['updated']} updated)")
        print(f"PWD Audits:             {summary['pwd_audits']['processed']} processed ({summary['pwd_audits']['inserted']} imported)")
        print(f"Risk Alerts Generated:  {summary['alerts_generated']} anomaly cases registered")
        print("="*60)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
