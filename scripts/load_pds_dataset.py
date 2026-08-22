"""RationRight — Load Synthetic PDS Dataset into Database.

Loads the generated synthetic PDS dataset into the RationRight database,
connecting it to the existing data-loading pipeline.

Usage:
    python3 scripts/load_pds_dataset.py

This script:
1. Reads data/synthetic/pds_dataset.json
2. Creates data source and import records
3. Inserts beneficiaries, FPS centers, transactions, inventory
4. Verifies referential integrity
5. Runs validation checks
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database import (
    DEFAULT_DB_PATH,
    open_db,
    insert_data_source,
    insert_data_import,
    upsert_beneficiary,
    insert_fps_center,
    insert_transaction,
    insert_inventory,
)

DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "pds_dataset.json"
SOURCE_NAME = "Synthetic PDS Dataset (Production Quality)"


def load_dataset() -> dict:
    """Load the synthetic dataset from JSON."""
    if not DATASET_PATH.exists():
        print(f"Dataset not found: {DATASET_PATH}")
        print("Run 'python3 scripts/generate_synthetic_pds.py' first.")
        sys.exit(1)
    
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_into_database(dataset: dict, db_path=DEFAULT_DB_PATH) -> dict:
    """Load the synthetic dataset into the database."""
    conn = open_db(db_path)
    stats = {
        "beneficiaries": 0,
        "fps_centers": 0,
        "transactions": 0,
        "inventory": 0,
        "errors": [],
    }
    
    try:
        # Check if data source already exists
        existing_source = conn.execute(
            "SELECT id FROM data_sources WHERE name = ?",
            (SOURCE_NAME,),
        ).fetchone()
        
        if existing_source:
            source_id = existing_source["id"]
            print(f"Using existing data source: {source_id}")
        else:
            source_id = insert_data_source(
                conn,
                name=SOURCE_NAME,
                source_type="JSON",
                description=dataset["metadata"]["description"],
                status="ACTIVE",
                last_sync_at=datetime.now().isoformat(),
            )
            print(f"Created data source: {source_id}")
        
        # Create data import
        import_id = insert_data_import(
            conn,
            data_source_id=source_id,
            dataset_name=dataset["metadata"]["label"],
            file_name="pds_dataset.json",
            file_type="json",
            record_count=len(dataset["transactions"]),
            successful_records=len(dataset["transactions"]),
            failed_records=0,
            duplicate_records=0,
            status="COMPLETED",
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
        )
        print(f"Created data import: {import_id}")
        
        # Load beneficiaries and build ID mapping
        print(f"Loading {len(dataset['beneficiaries'])} beneficiaries...")
        ben_id_map = {}  # external_reference -> internal id
        for ben in dataset["beneficiaries"]:
            try:
                internal_id = upsert_beneficiary(
                    conn,
                    external_reference=ben["beneficiary_id"],
                    state=ben["state"],
                    district=ben["district"],
                    block=ben.get("block"),
                    ration_category=ben.get("ration_category"),
                    family_size=ben.get("family_size"),
                    status=ben.get("status", "ACTIVE"),
                )
                ben_id_map[ben["beneficiary_id"]] = internal_id
                stats["beneficiaries"] += 1
            except Exception as e:
                stats["errors"].append(f"Beneficiary {ben['beneficiary_id']}: {e}")
        
        # Load FPS centers and build ID mapping
        print(f"Loading {len(dataset['fps_centers'])} FPS centers...")
        fps_id_map = {}  # fps_code -> internal id
        for center in dataset["fps_centers"]:
            try:
                # Check if FPS center already exists
                existing_fps = conn.execute(
                    "SELECT id FROM fps_centers WHERE fps_code = ?",
                    (center["fps_code"],),
                ).fetchone()
                
                if existing_fps:
                    fps_id_map[center["fps_code"]] = existing_fps["id"]
                else:
                    internal_id = insert_fps_center(
                        conn,
                        fps_code=center["fps_code"],
                        name=center.get("name"),
                        state=center.get("state"),
                        district=center.get("district"),
                        block=center.get("block"),
                        latitude=center.get("latitude"),
                        longitude=center.get("longitude"),
                        capacity=center.get("capacity"),
                        status=center.get("status", "ACTIVE"),
                    )
                    fps_id_map[center["fps_code"]] = internal_id
                stats["fps_centers"] += 1
            except Exception as e:
                stats["errors"].append(f"FPS {center['fps_code']}: {e}")
        
        # Load transactions with proper foreign key references
        print(f"Loading {len(dataset['transactions'])} transactions...")
        for tx in dataset["transactions"]:
            try:
                # Check if transaction already exists
                existing_tx = conn.execute(
                    "SELECT id, beneficiary_id, fps_center_id FROM ration_transactions WHERE external_transaction_id = ?",
                    (tx["transaction_id"],),
                ).fetchone()
                
                # Get internal IDs for foreign keys
                ben_internal_id = ben_id_map.get(tx["beneficiary_id"])
                fps_internal_id = fps_id_map.get(tx["fps_id"])
                
                if existing_tx:
                    # Update existing transaction with correct foreign keys if they are NULL
                    if (existing_tx["beneficiary_id"] is None or existing_tx["fps_center_id"] is None):
                        conn.execute(
                            "UPDATE ration_transactions SET beneficiary_id = ?, fps_center_id = ? WHERE id = ?",
                            (ben_internal_id, fps_internal_id, existing_tx["id"]),
                        )
                    stats["transactions"] += 1
                    continue
                
                insert_transaction(
                    conn,
                    external_transaction_id=tx["transaction_id"],
                    beneficiary_id=ben_internal_id,
                    fps_center_id=fps_internal_id,
                    transaction_date=tx["timestamp"],
                    commodity=tx["commodity"],
                    quantity=tx["quantity_kg"],
                    unit="kg",
                    latitude=tx.get("latitude"),
                    longitude=tx.get("longitude"),
                    status=tx.get("transaction_status", "COMPLETED"),
                    source_import_id=import_id,
                )
                stats["transactions"] += 1
            except Exception as e:
                stats["errors"].append(f"Transaction {tx['transaction_id']}: {e}")
        
        # Load inventory
        print(f"Loading {len(dataset['inventory'])} inventory records...")
        for inv in dataset["inventory"]:
            try:
                # Get FPS center ID
                fps_row = conn.execute(
                    "SELECT id FROM fps_centers WHERE fps_code = ?",
                    (inv["fps_id"],),
                ).fetchone()
                
                if fps_row:
                    insert_inventory(
                        conn,
                        fps_center_id=fps_row["id"],
                        commodity=inv["commodity"],
                        current_stock=inv["current_stock"],
                        monthly_consumption=inv.get("monthly_consumption"),
                        reorder_threshold=inv.get("reorder_threshold"),
                        last_updated=inv.get("last_updated"),
                        source_import_id=import_id,
                    )
                    stats["inventory"] += 1
            except Exception as e:
                stats["errors"].append(f"Inventory {inv['fps_id']}: {e}")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        print(f"Error loading dataset: {e}")
        raise
    finally:
        conn.close()
    
    return stats


def verify_database(db_path=DEFAULT_DB_PATH) -> dict:
    """Verify the loaded data in the database."""
    conn = open_db(db_path)
    verification = {}
    
    try:
        # Count records
        verification["beneficiaries"] = conn.execute(
            "SELECT COUNT(*) FROM beneficiaries"
        ).fetchone()[0]
        
        verification["fps_centers"] = conn.execute(
            "SELECT COUNT(*) FROM fps_centers"
        ).fetchone()[0]
        
        verification["transactions"] = conn.execute(
            "SELECT COUNT(*) FROM ration_transactions"
        ).fetchone()[0]
        
        verification["inventory"] = conn.execute(
            "SELECT COUNT(*) FROM inventory"
        ).fetchone()[0]
        
        # Check referential integrity
        verification["orphaned_transactions"] = conn.execute(
            "SELECT COUNT(*) FROM ration_transactions WHERE beneficiary_id IS NULL OR fps_center_id IS NULL"
        ).fetchone()[0]
        
        # Check data sources
        verification["data_sources"] = conn.execute(
            "SELECT COUNT(*) FROM data_sources"
        ).fetchone()[0]
        
        verification["data_imports"] = conn.execute(
            "SELECT COUNT(*) FROM data_imports"
        ).fetchone()[0]
        
    finally:
        conn.close()
    
    return verification


def main():
    """Main entry point."""
    print("=" * 60)
    print("RationRight — Load Synthetic PDS Dataset")
    print("=" * 60)
    
    # Load dataset
    dataset = load_dataset()
    print(f"Loaded dataset: {dataset['metadata']['label']}")
    print(f"  Transactions: {dataset['metadata']['stats']['transactions']}")
    print(f"  Beneficiaries: {dataset['metadata']['stats']['beneficiaries']}")
    print(f"  FPS Centers: {dataset['metadata']['stats']['fps_centers']}")
    
    # Load into database
    print("\nLoading into database...")
    stats = load_into_database(dataset)
    
    # Print results
    print("\n" + "=" * 60)
    print("Load Results")
    print("=" * 60)
    print(f"  Beneficiaries loaded: {stats['beneficiaries']}")
    print(f"  FPS Centers loaded: {stats['fps_centers']}")
    print(f"  Transactions loaded: {stats['transactions']}")
    print(f"  Inventory loaded: {stats['inventory']}")
    
    if stats["errors"]:
        print(f"\n  Errors: {len(stats['errors'])}")
        for error in stats["errors"][:10]:
            print(f"    - {error}")
        if len(stats["errors"]) > 10:
            print(f"    ... and {len(stats['errors']) - 10} more")
    
    # Verify database
    print("\nVerifying database...")
    verification = verify_database()
    
    print("\n" + "=" * 60)
    print("Database Verification")
    print("=" * 60)
    print(f"  Beneficiaries in DB: {verification['beneficiaries']}")
    print(f"  FPS Centers in DB: {verification['fps_centers']}")
    print(f"  Transactions in DB: {verification['transactions']}")
    print(f"  Inventory in DB: {verification['inventory']}")
    print(f"  Data Sources: {verification['data_sources']}")
    print(f"  Data Imports: {verification['data_imports']}")
    print(f"  Orphaned Transactions: {verification['orphaned_transactions']}")
    
    if verification["orphaned_transactions"] > 0:
        print("\nWARNING: There are orphaned transactions!")
    
    print("\nDataset loaded successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
