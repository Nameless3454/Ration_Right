"""
Authoritative data dictionary, schema descriptions, and system flag definitions
for the RationRight Public Distribution System platform.
"""
from typing import Any, Dict, List

DICTIONARY_CHUNKS: List[Dict[str, Any]] = [
    # 1. Welfare Categories & Quotas
    {
        "id": "quota_aay",
        "title": "Antyodaya Anna Yojana (AAY) Entitlement Quota",
        "category": "welfare_policy",
        "keywords": ["AAY", "Antyodaya", "quota", "entitlement", "poorest"],
        "content": (
            "Antyodaya Anna Yojana (AAY) is designated for the poorest of the poor households. "
            "Under the National Food Security Act (NFSA), the statutory entitlement quota is a flat "
            "35.0 kg of foodgrains per family per month, regardless of the number of family members. "
            "The standard composition is typically 20.0 kg Rice and 15.0 kg Wheat. Under PMGKAY, "
            "grains are provided free of cost."
        ),
    },
    {
        "id": "quota_phh",
        "title": "Priority Households (PHH) Entitlement Quota",
        "category": "welfare_policy",
        "keywords": ["PHH", "Priority Households", "quota", "entitlement", "per member"],
        "content": (
            "Priority Households (PHH) are eligible low-income families identified by state criteria. "
            "Under NFSA, the statutory quota is 5.0 kg of foodgrains per individual member per month. "
            "Formula: Total Monthly Grain (kg) = Family Member Count * 5.0 kg. For example, a family "
            "of 4 members receives 4 * 5 = 20.0 kg (typically 12 kg Rice + 8 kg Wheat)."
        ),
    },

    # 2. System Review Flags & Anomaly Rules
    {
        "id": "flag_possible_duplicate",
        "title": "Possible Duplicate Flag (identity_status = 'possible_duplicate')",
        "category": "system_flags",
        "keywords": ["possible_duplicate", "duplicate", "identity_status", "fingerprint"],
        "content": (
            "The 'possible_duplicate' flag indicates that two or more ration card records share an "
            "identical demographic or biometric fingerprint (e.g. matching iris, fingerprint scan, or "
            "household identity token). In RationRight demo data, records like BEN007 and BEN014 carry "
            "this flag. Every alert is strictly an administrative review lead, not proof of fraud. "
            "Field verification and appeal by the cardholder are mandatory before any entitlement action."
        ),
    },
    {
        "id": "flag_multiple_claims",
        "title": "Multiple Claims Flag (collection_status = 'multiple_claims')",
        "category": "system_flags",
        "keywords": ["multiple_claims", "collection_status", "repeated transaction", "double claim"],
        "content": (
            "The 'multiple_claims' flag is triggered when two or more successful grain distribution "
            "transactions are recorded for the same beneficiary and commodity within the same entitlement "
            "month/period. In the synthetic dataset, BEN019 has two Rice collections on 2026-10-12 via "
            "manual override. It indicates an operational anomaly that requires physical ledger audit."
        ),
    },
    {
        "id": "alert_stock_mismatch",
        "title": "Stock Mismatch Anomaly",
        "category": "system_flags",
        "keywords": ["stock mismatch", "inventory discrepancy", "physical stock", "closing stock"],
        "content": (
            "A Stock Mismatch occurs when the physical grain stock counted during ground inspection differs "
            "from the expected book closing stock. Formula: Expected Closing Stock = Opening Stock + "
            "Received Stock - Distributed Stock. Physical Discrepancy = Physical Stock - Expected Closing. "
            "A negative discrepancy indicates a physical shortage (e.g. -280 kg Rice at PWD002)."
        ),
    },
    {
        "id": "channel_manual_override",
        "title": "Manual Override Transaction Channel",
        "category": "system_flags",
        "keywords": ["manual_override", "biometric", "channel", "ePOS override"],
        "content": (
            "Distribution transactions normally authenticate through biometric Aadhaar fingerprint or iris "
            "scanners at the electronic Point of Sale (ePOS). When biometric authentication fails due to "
            "worn fingerprints, scanner breakdown, or severe connectivity loss, dealers may execute a "
            "'manual_override'. While permitted as a fallback, high manual override counts (e.g. PWD004 with 7) "
            "trigger audit scrutiny."
        ),
    },

    # 3. Schema & Entity Definitions
    {
        "id": "schema_pwd_shops",
        "title": "Fair Price Shops (pwd_shops) Entity Schema",
        "category": "schema_documentation",
        "keywords": ["pwd_shops", "fair price shop", "FPS", "dealer", "monthly_capacity_kg"],
        "content": (
            "The 'pwd_shops' table represents licensed Fair Price Shops (FPS) / Public Wholesale Distribution "
            "centers. Fields include: pwd_id (unique outlet identifier), shop_name (outlet name), dealer_id "
            "(licensee ID), district and state (geographic location), monthly_capacity_kg (statutory storage "
            "and distribution quota limit in kg), and gps_lat/gps_lon (geospatial coordinates)."
        ),
    },
    {
        "id": "schema_inventory",
        "title": "Inventory Stock Ledger Schema",
        "category": "schema_documentation",
        "keywords": ["inventory", "opening_stock_kg", "closing_stock_kg", "physical_stock_kg", "received_kg"],
        "content": (
            "The 'inventory' table tracks monthly grain receipts, disbursements, and balances per shop and "
            "commodity. Fields include: inventory_id (unique record ID), pwd_id (shop), month (reporting period "
            "e.g. 2026-10), commodity (Rice or Wheat), opening_stock_kg (carryover from previous month), "
            "received_kg (grain delivered from FCI silos), distributed_kg (grain disbursed to beneficiaries), "
            "closing_stock_kg (calculated ledger balance), and physical_stock_kg (actual physical audit count)."
        ),
    },
    {
        "id": "schema_beneficiaries",
        "title": "Beneficiaries Registry Schema",
        "category": "schema_documentation",
        "keywords": ["beneficiaries", "ration_card_id", "head_name", "category", "family_size"],
        "content": (
            "The 'beneficiaries' table represents registered citizen households under NFSA. Fields include: "
            "beneficiary_id (unique ID), ration_card_id (ration card number), head_name (name of household head), "
            "family_size (number of members), category (PHH or AAY), pwd_id (assigned FPS shop), "
            "monthly_entitlement_kg (allocated monthly grain), last_collection_date, collection_status, "
            "identity_status (verified, possible_duplicate, review_required), and review_reason."
        ),
    },
    {
        "id": "schema_pwd_audits",
        "title": "Fair Price Shop Audits & Compliance Schema",
        "category": "schema_documentation",
        "keywords": ["pwd_audits", "complaints_count", "late_opening_days", "inspection_status"],
        "content": (
            "The 'pwd_audits' table records monthly compliance telemetry and inspection outcomes for each shop. "
            "Fields include: audit_id, pwd_id, period, late_opening_days (days the shop opened past mandated hours), "
            "manual_override_count (distributions without biometrics), complaints_count (citizen grievances "
            "registered via helpline), and inspection_status (passed, pending, failed)."
        ),
    },
    {
        "id": "schema_transactions",
        "title": "Distribution Issuance Transactions Schema",
        "category": "schema_documentation",
        "keywords": ["transactions", "transaction_id", "channel", "quantity_kg", "commodity"],
        "content": (
            "The 'transactions' table records every individual grain disbursal at the ePOS terminal. Fields: "
            "transaction_id, beneficiary_id, pwd_id, date, commodity (Rice/Wheat), quantity_kg (weight issued), "
            "channel (biometric or manual_override), and status (success)."
        ),
    },

    # 4. Governance & Administrative Boundaries
    {
        "id": "governance_boundaries",
        "title": "RationRight Administrative Boundaries & Fraud Disclaimer",
        "category": "governance",
        "keywords": ["fraud", "official authority", "disclaimer", "investigation", "legal decision"],
        "content": (
            "Under NFSA guidelines and RationRight operating boundaries: AI assistants and automated models "
            "must NEVER declare a beneficiary 'fraudulent', 'corrupt', or guilty of a crime. All system flags "
            "(such as possible_duplicate or stock mismatch) are purely operational review leads for human field "
            "inspectors. Final legal, administrative, and benefit determination decisions rest exclusively with "
            "authorized government officials."
        ),
    },
]

