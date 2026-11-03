"""
Phase 0 Dataset Inspection Script
Audits RationRight synthetic dummy dataset: schemas, foreign keys, and anomalies.
"""
import csv
import json
from pathlib import Path

DATA_PACK_DIR = Path(__file__).resolve().parent.parent.parent / "rationright-rag" / "RationRight_Dummy_Data_Pack"
if not DATA_PACK_DIR.exists():
    DATA_PACK_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploaded_dataset"

def inspect_csv(file_name):
    file_path = DATA_PACK_DIR / file_name
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows

def run_inspection():
    print(f"=== RationRight Phase 0 Dataset Audit ===")
    print(f"Source Directory: {DATA_PACK_DIR}\n")

    # 1. Inspect PWD Shops
    shops = inspect_csv("pwd_shops.csv")
    print(f"[1] pwd_shops.csv: {len(shops)} records")
    print(f"    Fields: {list(shops[0].keys())}")
    shop_ids = {s['pwd_id'] for s in shops}
    print(f"    Shop IDs: {sorted(list(shop_ids))}\n")

    # 2. Inspect Beneficiaries
    beneficiaries = inspect_csv("beneficiaries.csv")
    print(f"[2] beneficiaries.csv: {len(beneficiaries)} records")
    print(f"    Fields: {list(beneficiaries[0].keys())}")
    ben_ids = {b['beneficiary_id'] for b in beneficiaries}
    ben_shop_ids = {b['pwd_id'] for b in beneficiaries}
    unmatched_ben_shops = ben_shop_ids - shop_ids
    print(f"    Foreign key check (beneficiaries.pwd_id -> pwd_shops): {len(unmatched_ben_shops)} unmatched")
    
    # Check flags
    dup_flags = [b for b in beneficiaries if b.get('identity_status') == 'possible_duplicate']
    print(f"    Records with identity_status='possible_duplicate': {len(dup_flags)}")
    for d in dup_flags:
        print(f"      - {d['beneficiary_id']} (Shop: {d['pwd_id']}, Card: {d['ration_card_id']}): {d.get('review_reason')}")
    
    multi_flags = [b for b in beneficiaries if b.get('collection_status') == 'multiple_claims']
    print(f"    Records with collection_status='multiple_claims': {len(multi_flags)}")
    for m in multi_flags:
        print(f"      - {m['beneficiary_id']}: {m.get('review_reason')}\n")

    # 3. Inspect Inventory
    inventory = inspect_csv("inventory.csv")
    print(f"[3] inventory.csv: {len(inventory)} records")
    print(f"    Fields: {list(inventory[0].keys())}")
    inv_discrepancies = []
    for inv in inventory:
        opening = int(inv['opening_stock_kg'])
        received = int(inv['received_kg'])
        distributed = int(inv['distributed_kg'])
        closing = int(inv['closing_stock_kg'])
        physical = int(inv['physical_stock_kg'])
        expected = opening + received - distributed
        discrepancy = physical - expected
        if discrepancy != 0:
            inv_discrepancies.append((inv['inventory_id'], inv['pwd_id'], inv['commodity'], expected, physical, discrepancy))
    print(f"    Physical Stock Shortages/Surpluses found: {len(inv_discrepancies)} records")
    for inv_id, shop_id, comm, exp, phys, diff in inv_discrepancies:
        print(f"      - {inv_id} ({shop_id} {comm}): Expected Book Closing={exp} kg, Physical Stock={phys} kg (Discrepancy: {diff} kg)")
    print()

    # 4. Inspect Transactions
    txns = inspect_csv("transactions.csv")
    print(f"[4] transactions.csv: {len(txns)} records")
    print(f"    Fields: {list(txns[0].keys())}")
    txn_ben_ids = {t['beneficiary_id'] for t in txns}
    unmatched_txns = txn_ben_ids - ben_ids
    print(f"    Foreign key check (transactions.beneficiary_id -> beneficiaries): {len(unmatched_txns)} unmatched")
    manual_txns = [t for t in txns if t.get('channel') == 'manual_override']
    print(f"    Transactions with channel='manual_override': {len(manual_txns)}")
    for t in manual_txns:
        print(f"      - {t['transaction_id']}: Beneficiary={t['beneficiary_id']}, Date={t['date']}, Qty={t['quantity_kg']}kg {t['commodity']}")
    print()

    # 5. Inspect PWD Audits
    audits = inspect_csv("pwd_audits.csv")
    print(f"[5] pwd_audits.csv: {len(audits)} records")
    print(f"    Fields: {list(audits[0].keys())}")
    for a in audits:
        print(f"      - Shop {a['pwd_id']}: Inspection={a['inspection_status']}, Complaints={a['complaints_count']}, Late Opening Days={a['late_opening_days']}, Overrides={a['manual_override_count']}")
    print()

    # 6. Inspect JSON
    json_path = DATA_PACK_DIR / "rationright_demo_data.json"
    with open(json_path, "r", encoding="utf-8") as f:
        demo_json = json.load(f)
    print(f"[6] rationright_demo_data.json metadata:")
    for k, v in demo_json.get('metadata', {}).items():
        print(f"      {k}: {v}")

if __name__ == "__main__":
    run_inspection()

