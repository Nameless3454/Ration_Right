"""RationRight — column detection and schema mapping (Phase 3).

External government/Excel datasets rarely use RationAI's internal field names
(``fps_code`` vs ``FPS_ID``, ``district`` vs ``District Name``, ``quantity``
vs ``Qty Distributed``). This module maps external column names onto the
normalized internal schema from Phase 2 WITHOUT creating a table per dataset.

Matching is case/whitespace/punctuation-insensitive: headers are normalized
(e.g. ``District Name`` -> ``districtname``) and compared against a curated,
extendable alias table (``FIELD_ALIASES``). Unknown columns map to
``ignore``. Automatic mapping is a suggestion — the user can override any
column in the mapping UI, and required fields are clearly marked.
"""

from __future__ import annotations

import re

from ingestion.parsers import ParseError

# Dataset kinds the importer understands.
DATASET_TYPES = ("beneficiaries", "fps_centers", "ration_transactions", "inventory", "combined", "operational_summary")

DATASET_TYPE_LABELS = {
    "beneficiaries": "Beneficiaries",
    "fps_centers": "FPS Centers",
    "ration_transactions": "Ration Transactions",
    "inventory": "Inventory",
    "combined": "Combined Dataset",
    "operational_summary": "Operational / District Summary",
}

# Human-readable labels for the internal fields (used by the mapping UI).
FIELD_LABELS = {
    "external_reference": "Beneficiary ID",
    "fps_code": "FPS Code",
    "name": "Center Name",
    "external_transaction_id": "Transaction ID",
    "beneficiary_id": "Beneficiary ID (ref)",
    "fps_center_id": "FPS Code (ref)",
    "transaction_date": "Transaction Date",
    "commodity": "Commodity",
    "quantity": "Quantity",
    "unit": "Unit",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "state": "State",
    "district": "District",
    "block": "Block",
    "location": "Location",
    "capacity": "Capacity",
    "ration_category": "Ration Category",
    "family_size": "Family Size",
    "current_stock": "Current Stock",
    "monthly_consumption": "Monthly Consumption",
    "reorder_threshold": "Reorder Threshold",
    "last_updated": "Last Updated",
    "status": "Status",
}

# Which internal fields are mappable per dataset type.
FIELDS_BY_TYPE = {
    "beneficiaries": (
        "external_reference", "state", "district", "block",
        "ration_category", "family_size", "status",
    ),
    "fps_centers": (
        "fps_code", "name", "state", "district", "block", "location",
        "latitude", "longitude", "capacity", "status",
    ),
    "ration_transactions": (
        "external_transaction_id", "beneficiary_id", "fps_center_id",
        "transaction_date", "commodity", "quantity", "unit",
        "latitude", "longitude", "status",
        # Beneficiary/center detail columns are accepted on transaction files:
        "state", "district", "block", "ration_category", "family_size",
        "name", "location",
    ),
    "inventory": (
        "fps_center_id", "commodity", "current_stock",
        "monthly_consumption", "reorder_threshold", "last_updated",
    ),
    "combined": (
        "external_transaction_id", "beneficiary_id", "fps_center_id",
        "transaction_date", "commodity", "quantity", "unit",
        "latitude", "longitude", "status",
        "external_reference", "state", "district", "block",
        "ration_category", "family_size",
        "name", "location", "capacity",
    ),
    "operational_summary": (
        "district", "total_cards", "biometric_transactions",
        "aadhaar_otp_transactions", "mobile_otp_transactions",
        "iris_transactions", "partial_offline_transactions",
        "total_transactions", "portability_transactions",
        "online_transactions", "total_availed_percent",
        "partial_percent", "report_date", "state",
    ),
}

# Required internal fields per dataset type (documented Phase 4 rules).
# Transaction IDs stay OPTIONAL — a deterministic composite key is used when
# no ID column exists (see ingestion.importer._dedup_key).
REQUIRED_FIELDS = {
    "beneficiaries": ("external_reference", "district", "family_size", "ration_category"),
    "fps_centers": ("fps_code", "district"),
    "ration_transactions": ("fps_center_id", "transaction_date", "commodity", "quantity"),
    "inventory": ("fps_center_id", "commodity", "current_stock"),
    "combined": ("fps_center_id", "transaction_date", "commodity", "quantity"),
    "operational_summary": ("district",),
}

# Extendable alias table: internal field -> accepted external names
# (normalized form: lowercase, alphanumerics only). The internal name is
# always accepted automatically.
FIELD_ALIASES = {
    "external_reference": {
        "beneficiaryid", "beneficiary", "beneficiaryref", "beneficiaryreference",
        "bid", "cardno", "rationcardno", "rationcardid", "bplcardno",
        "beneficiarycode", "uniqueid", "hhid", "householdid", "uid",
    },
    "fps_code": {
        "fpscode", "fpsid", "fps", "fairpriceshop", "fairpriceshopcode",
        "fairpriceshopid", "shopcode", "shopid", "centerid", "center",
        "fpscenter", "fpscenterid", "distributioncenterid", "dccode", "outletcode",
    },
    "name": {"name", "shopname", "fpsname", "centername", "outletname", "shop"},
    "external_transaction_id": {
        "transactionid", "txid", "receiptno", "receiptnumber", "transactionno",
        "tokenno", "slipno", "distributionid", "invoiceid", "billno", "id",
        "serialno", "serialnumber", "vouchernumber",
    },
    "beneficiary_id": {
        "beneficiaryid", "beneficiary", "beneficiaryref", "bid", "cardno",
        "rationcardno", "beneficiarycode", "hhid",
    },
    "fps_center_id": {
        "fpsid", "fps", "fairpriceshopcode", "shopcode", "centerid", "center",
        "fpscenter", "fpscode", "outletcode",
        "fps_id", "fpsname", "fps_name", "fairpriceshopname",
        "shopname", "shop_name", "distributioncenter",
        "fpscentre", "fps_centre",
    },
    "transaction_date": {
        "transactiondate", "date", "datedistributed", "distributiondate",
        "timestamp", "txdate", "dateofdistribution", "transactiontime",
        "distributedon", "saledate", "issuedate",
        "transaction_date", "distribution_date", "distributiondate",
        "date_of_distribution", "txdate", "transdate",
        "trans_date", "date_time", "datetime", "transactedon",
    },
    "commodity": {
        "commodity", "rationtype", "item", "itemname", "commodityname",
        "grain", "product", "material", "ration", "commoditytype", "itemtype",
        "goodstype", "commoditycode",
        "commodity_name", "item_name", "product_name",
        "commoditytype", "distributiontype", "distribution_type",
        "ration_type", "food_item", "fooditem",
    },
    "quantity": {
        "quantity", "qty", "qtydistributed", "quantitydistributed", "amount",
        "quantitykg", "distributedqty", "kg", "quantityissued", "issueqty",
        "units", "quantityinkg", "weight", "qtyissued",
        "quantity_kg", "qty_kg", "distributed_quantity",
        "distribution_qty", "issue_quantity", "issued_qty",
        "weight_kg", "total_qty", "total_quantity",
        "quantitydistributedkg", "qtydistributedkg",
        "weightkg", "totalqty", "distributedquantity",
        "distributionquantity", "quantitydispensed",
    },
    "unit": {"unit", "units", "uom", "unitofmeasure"},
    "latitude": {"latitude", "lat", "latitudevalue"},
    "longitude": {"longitude", "lon", "lng", "long", "longitudevalue"},
    "state": {"state", "statename", "st"},
    "district": {"district", "districtname", "dist", "districtcode", "districtid"},
    "block": {"block", "blockname", "tehsil", "taluk", "mandal"},
    "location": {"location", "address", "locality", "villagename", "village", "area", "sector"},
    "capacity": {"capacity", "storagecapacity", "maxcapacity", "capacitykg", "storagelimit"},
    "ration_category": {
        "rationcategory", "category", "cardcategory", "rationcardcategory",
        "aaycategory", "householdcategory", "prioritycategory",
    },
    "family_size": {
        "familysize", "householdsize", "noofmembers", "members", "familymembers",
        "totalmembers",
    },
    "current_stock": {
        "currentstock", "stock", "closingstock", "stockonhand", "available",
        "balance", "inventory", "openingstock", "closingbalance", "stockqty",
    },
    "monthly_consumption": {
        "monthlyconsumption", "consumption", "avgmonthlyconsumption",
        "monthlyusage", "monthlyconsumptionqty", "consumptionrate",
    },
    "reorder_threshold": {
        "reorderthreshold", "threshold", "reorderlevel", "minstock",
        "safetystock", "minimumstock", "reorderpoint",
    },
    "last_updated": {
        "lastupdated", "updated", "asof", "reportdate", "stockdate", "updatedate",
    },
    "status": {"status", "recordstatus", "stateflag"},
    # Operational summary fields
    "total_cards": {
        "totalcards", "total_cards", "cards", "noofcards", "numberofcards",
        "totalbeneficiaries", "total_beneficiaries", "beneficiarycount",
        "beneficiary_count", "cardholders", "card_holders", "totalcard",
    },
    "biometric_transactions": {
        "biometric", "biometric_transactions", "biometrictx", "biometriccount",
        "biometric_count", "bio_auth", "biometric_auth",
    },
    "aadhaar_otp_transactions": {
        "aadharotp", "aadhaarotp", "aadhaar_otp", "aadhaar_otp_transactions",
        "aadhaarotptx", "aadhaarotcount", "aadharotpcount",
        "aadhaarotpcount", "aadhaar_otp_count", "aadharnotp",
    },
    "mobile_otp_transactions": {
        "mobileotp", "mobile_otp", "mobile_otp_transactions",
        "mobileotptx", "mobileotcount", "mobileotpcount",
        "mobile_otp_count", "smsotp", "sms_otp",
    },
    "iris_transactions": {
        "iris", "iris_transactions", "iristx", "iriscount",
        "iris_count", "iris_auth",
    },
    "partial_offline_transactions": {
        "partialoffline", "partial_offline", "partial_offline_transactions",
        "partialofflinetx", "partialofflinecount", "partial_offline_count",
    },
    "total_transactions": {
        "total", "total_transactions", "totaltx", "grandtotal",
        "grand_total", "totalcount", "total_count",
    },
    "portability_transactions": {
        "portability", "portability_transactions", "portabilitytx",
        "portabilitycount", "portability_count", "portable",
    },
    "online_transactions": {
        "online", "online_transactions", "onlinetx", "onlinecount",
        "online_count", "online_auth",
    },
    "total_availed_percent": {
        "totalavailedpercent", "total_availed_percent", "availedpercent",
        "availed_percent", "pctavailed", "pct_availed",
        "availedpct", "totalavailed", "total_availed",
    },
    "partial_percent": {
        "partialpercent", "partial_percent", "partialpct",
        "partialpct", "partial", "partialp",
    },
    "report_date": {
        "reportdate", "report_date", "reportingdate", "reporting_date",
        "asofdate", "as_of_date", "data_date", "period",
    },
}

# Fields whose values are constrained to an enumeration (validated at import).
STATUS_ALLOWED = {
    "beneficiaries": ("ACTIVE", "INACTIVE"),
    "fps_centers": ("ACTIVE", "INACTIVE"),
    "ration_transactions": ("COMPLETED", "PENDING", "FAILED", "CANCELLED"),
    "inventory": (),
    "combined": ("COMPLETED", "PENDING", "FAILED", "CANCELLED"),
    "operational_summary": (),
}


class MappingError(ParseError):
    """Raised when a mapping is missing required fields or is malformed."""


def normalize_header(name) -> str:
    """Lowercase and keep alphanumerics: 'District Name' -> 'districtname'."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def mappable_fields(dataset_type: str) -> tuple:
    return FIELDS_BY_TYPE.get(dataset_type, FIELDS_BY_TYPE["ration_transactions"])


def required_fields(dataset_type: str) -> tuple:
    return REQUIRED_FIELDS.get(dataset_type, REQUIRED_FIELDS["ration_transactions"])


def _alias_set(field: str) -> set:
    return {field} | FIELD_ALIASES.get(field, set())


def detect_mapping(headers: list, dataset_type: str) -> dict:
    """Auto-map external headers to internal fields.

    Returns ``{"mapping": [{"external": ..., "internal": ...|None}, ...],
    "warnings": [...], "missing_required": [...]}``. The first column that
    matches a field wins; unknown columns map to ``None`` (ignore)."""
    if dataset_type not in DATASET_TYPES:
        raise MappingError(
            "Unknown dataset type %r. Supported: %s"
            % (dataset_type, ", ".join(DATASET_TYPES))
        )
    fields = mappable_fields(dataset_type)
    aliases = {field: _alias_set(field) for field in fields}
    used = set()
    mapping = []
    warnings = []
    for header in headers:
        normalized = normalize_header(header)
        internal = None
        if normalized:
            for field, accepted in aliases.items():
                if field not in used and normalized in accepted:
                    internal = field
                    used.add(field)
                    break
            if normalized in ("ignore", "ignored", "unused"):
                warnings.append("Column %r marked as ignored." % header)
        mapping.append({"external": header, "internal": internal})

    missing_required = [
        field for field in required_fields(dataset_type)
        if field not in {m["internal"] for m in mapping}
    ]
    return {"mapping": mapping, "warnings": warnings, "missing_required": missing_required}


def infer_dataset_type(headers: list) -> str:
    """Guess the dataset kind from the columns present.

    Order of checks: operational summary (district + total_cards/total columns,
    no commodity/quantity), inventory (stock columns, no quantity), transactions
    (commodity + quantity/date), FPS centers (fps code, no commodity),
    beneficiaries (beneficiary ref, no quantity), default transactions."""
    normalized = {normalize_header(h) for h in headers if normalize_header(h)}
    has = lambda field, aliases: bool(normalized & (set(aliases) | {field}))

    # Operational summary: has district AND total_cards or total columns,
    # but no commodity or quantity columns (district-level summary report).
    has_district = has("district", FIELD_ALIASES["district"])
    has_total_cards = has("total_cards", FIELD_ALIASES["total_cards"])
    has_total_tx = has("total_transactions", FIELD_ALIASES["total_transactions"])
    has_biometric = has("biometric_transactions", FIELD_ALIASES["biometric_transactions"])
    has_stock = has("current_stock", FIELD_ALIASES["current_stock"])
    has_quantity = has("quantity", FIELD_ALIASES["quantity"])
    has_commodity = has("commodity", FIELD_ALIASES["commodity"])
    has_date = has("transaction_date", FIELD_ALIASES["transaction_date"])
    has_fps = has("fps_code", FIELD_ALIASES["fps_code"])
    has_beneficiary = has("external_reference", FIELD_ALIASES["external_reference"])

    if has_stock and not has_quantity and has_commodity:
        return "inventory"
    if has_commodity and (has_quantity or has_date):
        return "ration_transactions"
    if has_fps and not has_commodity:
        return "fps_centers"
    if has_beneficiary and not has_quantity:
        return "beneficiaries"
    # Operational summary: district-level aggregate report (has district + total
    # or biometric columns, but NOT transaction-level commodity/quantity data).
    if has_district and (has_total_cards or has_total_tx or has_biometric):
        return "operational_summary"
    return "ration_transactions"


def validate_mapping(mapping: list, dataset_type: str) -> list:
    """Return errors (list of strings) if the mapping is unusable.

    ``mapping`` is a list of ``{"external": ..., "internal": ...}`` dicts."""
    if not isinstance(mapping, list):
        raise MappingError("Mapping must be a list of column assignments.")
    mapped = []
    for entry in mapping:
        if not isinstance(entry, dict) or "external" not in entry:
            raise MappingError("Malformed mapping entry: %r" % (entry,))
        internal = entry.get("internal")
        if internal is None or internal in ("", "ignore"):
            continue
        fields = mappable_fields(dataset_type)
        if internal not in fields:
            raise MappingError(
                "Column %r maps to unknown field %r (allowed for %s: %s)"
                % (entry["external"], internal, dataset_type, ", ".join(fields))
            )
        if internal in mapped:
            raise MappingError(
                "Multiple columns map to the same field %r; each internal field "
                "may be used once." % internal
            )
        mapped.append(internal)

    missing = [f for f in required_fields(dataset_type) if f not in mapped]
    if missing:
        labels = ", ".join(field_label(f) for f in missing)
        return [
            "Required field(s) are not mapped: %s. "
            "Use the dropdowns in the column mapping table above to assign each "
            "required column to the correct RationRight field, then click "
            "\"Validate & preview\" again." % labels
        ]
    return []


def mapping_to_dict(mapping: list) -> dict:
    """Convert the mapping list into ``{external: internal}`` for the importer."""
    result = {}
    for entry in mapping:
        internal = entry.get("internal")
        if internal and internal != "ignore":
            result[entry["external"]] = internal
    return result
