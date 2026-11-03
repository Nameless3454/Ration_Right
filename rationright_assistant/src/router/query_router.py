"""
Question router for RationRight AI Assistant.
Classifies user queries into structured SQL, RAG definition, hybrid, or unsupported,
and retrieves verified evidence from SQLite and ChromaDB.
"""
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from src.config import settings
from src.db.database import get_db_connection
from src.models.schemas import QueryRequest, RouteType, RoutedQueryContext
from src.query_engine.comparator import compare_snapshots
from src.query_engine.safe_queries import (
    get_audit_summary,
    get_beneficiaries_summary,
    get_beneficiary_by_id,
    get_flagged_beneficiaries,
    get_import_summary,
    get_inventory_status,
    get_latest_import_id,
    get_shop_complaints_ranking,
    get_shop_or_dealer_by_id,
    get_transactions_summary,
)
from src.rag.vector_store import DictionaryRetriever, get_retriever


PDS_DOMAIN_KEYWORDS = [
    "beneficiary", "beneficiaries", "card", "cards", "shop", "shops", "inventory",
    "stock", "audit", "audits", "transaction", "transactions", "quota", "quotas",
    "rice", "wheat", "summary", "status", "pwd", "fps", "dealer", "dealers",
    "dlr", "ration", "entitlement", "entitlements", "distribution", "commodity",
    "grain", "grains", "inspection", "inspections", "complaint", "complaints",
    "override", "overrides", "biometric", "phh", "aay", "allocation", "discrepancy",
    "shortage", "surplus", "variance", "duplicate", "claim", "claims", "dataset",
    "import", "fair price", "food security", "record", "records",
]

CONTEXTUAL_FOLLOW_UP_PATTERNS = [
    r"\bwhy\b",
    r"\bwhich one\b",
    r"\bwhich ones\b",
    r"\bshow details\b",
    r"\btell me more\b",
    r"\bhow so\b",
    r"\bwhat about the others\b",
    r"\bexpand on this\b",
    r"\bwho are they\b",
    r"\bgive me more details\b",
    r"\belaborate\b",
    r"\bmore details\b",
    r"\bexplain further\b",
    r"\bwhat happened\b",
]

ACCUSATORY_TOKENS = [
    "fraud", "corrupt", "corruption", "scam", "criminal", "guilty",
    "stole", "stealing", "illegal", "bribe", "theft", "accuse",
]


class QueryRouter:
    """Routes user queries to safe SQL execution, ChromaDB semantic search, or hybrid retrieval."""

    def __init__(self, db_path: Optional[Path] = None, retriever: Optional[DictionaryRetriever] = None):
        self.db_path = db_path or settings.DB_PATH
        self.retriever = retriever or get_retriever()

    def route_and_resolve(self, request: QueryRequest) -> RoutedQueryContext:
        """Analyze query, determine intent, execute data fetch, and package context."""
        question = request.question.strip()
        q_lower = question.lower()

        # 1. Resolve import_id
        target_import_id = request.import_id
        if not target_import_id or target_import_id == "latest":
            target_import_id = get_latest_import_id(self.db_path)

        summary = get_import_summary(target_import_id, self.db_path) if target_import_id else None
        dataset_name = summary["dataset_name"] if summary else None

        # 2. Check for Unsupported / Out-of-Domain queries
        if self._is_unsupported(q_lower):
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.UNSUPPORTED,
                intent="OUT_OF_DOMAIN",
                is_supported=False,
                sql_data=None,
                rag_context=None,
            )

        # 3. Check for Missing Commodity Inquiries
        unsupported_commodity = self._detect_unsupported_commodity(q_lower)
        if unsupported_commodity:
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="UNSUPPORTED_COMMODITY",
                is_supported=False,
                sql_data={
                    "error": f"The imported RationRight datasets only track Rice and Wheat. No records exist for '{unsupported_commodity}'."
                },
                import_id_cited=target_import_id,
                dataset_name_cited=dataset_name,
            )

        # 4. Check for Specific Entity Inquiry (BEN, PWD, DLR) / Fraud Accusation Defense
        entity_match = re.search(r"\b(BEN\d+|PWD\d+|DLR\d+)\b", question, re.IGNORECASE)
        is_accusatory = any(
            re.search(r"\b" + re.escape(k) + r"\b", q_lower)
            for k in ACCUSATORY_TOKENS
        )

        if entity_match:
            entity_id = entity_match.group(1).upper()
            if entity_id.startswith("BEN"):
                record = get_beneficiary_by_id(target_import_id, entity_id, db_path=self.db_path) if target_import_id else None
                intent = "BENEFICIARY_FRAUD_INQUIRY" if is_accusatory else "BENEFICIARY_RECORD_LOOKUP"
                return RoutedQueryContext(
                    question=question,
                    route_type=RouteType.STRUCTURED,
                    intent=intent,
                    sql_data={
                        "beneficiary": record,
                        "beneficiary_id": entity_id,
                        "entity_type": "beneficiary",
                        "is_accusation": is_accusatory,
                    },
                    import_id_cited=target_import_id,
                    dataset_name_cited=dataset_name,
                )
            else:  # PWD or DLR
                record = get_shop_or_dealer_by_id(target_import_id, entity_id, db_path=self.db_path) if target_import_id else None
                intent = "SHOP_FRAUD_INQUIRY" if is_accusatory else "SHOP_RECORD_LOOKUP"
                return RoutedQueryContext(
                    question=question,
                    route_type=RouteType.STRUCTURED,
                    intent=intent,
                    sql_data={
                        "shop": record,
                        "entity_id": entity_id,
                        "entity_type": "shop_or_dealer",
                        "is_accusation": is_accusatory,
                    },
                    import_id_cited=target_import_id,
                    dataset_name_cited=dataset_name,
                )

        # 4b. Check for General Fraud / Accusation Inquiries without a specific ID
        if is_accusatory:
            if any(k in q_lower for k in ["shop", "dealer", "dlr", "pwd", "fps", "store", "merchant"]):
                ranking = get_shop_complaints_ranking(target_import_id, limit=5, db_path=self.db_path) if target_import_id else []
                return RoutedQueryContext(
                    question=question,
                    route_type=RouteType.STRUCTURED,
                    intent="SHOP_FRAUD_INQUIRY",
                    sql_data={"ranking": ranking, "is_accusation": True},
                    import_id_cited=target_import_id,
                    dataset_name_cited=dataset_name,
                )
            else:
                records = get_flagged_beneficiaries(target_import_id, flag_type="possible_duplicate", db_path=self.db_path) if target_import_id else []
                return RoutedQueryContext(
                    question=question,
                    route_type=RouteType.STRUCTURED,
                    intent="BENEFICIARY_FRAUD_INQUIRY",
                    sql_data={"records": records, "is_accusation": True},
                    import_id_cited=target_import_id,
                    dataset_name_cited=dataset_name,
                )

        # 5. Check for Snapshot Comparison Queries
        if self._is_comparison_query(q_lower):
            return self._handle_comparison(request, question, target_import_id, dataset_name)

        # 6. Check for Hybrid Queries (both data records and definition explanation)
        if self._is_hybrid_query(q_lower):
            return self._handle_hybrid(question, q_lower, target_import_id, dataset_name)

        # 7. Check for Definition / Policy RAG Queries
        if self._is_definition_query(q_lower):
            return self._handle_rag_definition(question, q_lower, target_import_id, dataset_name)

        # 8. Structured SQL Queries
        return self._handle_structured(question, q_lower, target_import_id, dataset_name)

    def _detect_unsupported_commodity(self, q: str) -> Optional[str]:
        """Detect commodities not tracked in RationRight (which only stocks Rice and Wheat)."""
        commodities = ["sugar", "kerosene", "pulses", "dal", "cooking oil", "edible oil", "salt", "mustard oil"]
        for c in commodities:
            if re.search(r"\b" + re.escape(c) + r"\b", q):
                return c
        return None

    def _is_unsupported(self, q: str) -> bool:
        """Detect out-of-domain queries that cannot be answered from RationRight data."""
        unsupported_patterns = [
            r"\bcapital of\b", r"\bweather\b", r"\bstock (?:price|market|ticker|symbol|exchange|quote)\b",
            r"\bshares of\b", r"\bcompany stock\b", r"\bcrypto\b", r"\bbitcoin\b",
            r"\bpresident of\b", r"\bprime minister\b", r"\bmovie\b", r"\brecipe\b", r"\bpoem\b",
            r"\bwrite code\b", r"\bwrite a (?:python|javascript|java|c\+\+|bash)? ?(?:script|program|code)\b",
            r"\bpython script\b", r"\bhow to (?:bake|cook|make|code|build|program)\b",
            r"\bfootball\b", r"\bcricket match\b", r"\bpredict future\b",
            r"\bworld cup\b", r"\bwho is elon\b", r"\btell me a joke\b",
        ]
        return any(re.search(pat, q) for pat in unsupported_patterns)

    def _is_comparison_query(self, q: str) -> bool:
        """Detect questions asking for week-over-week comparisons or record changes."""
        comparison_patterns = [
            r"\bcompare\b",
            r"\bwhich (?:inventory|records|beneficiaries) have changed\b",
            r"\bchanged\b",
            r"\bvariance\b",
            r"\bdifference between\b",
            r"\blast week\b",
            r"\bprevious week\b",
            r"\bweek[- ]over[- ]week\b",
            r"\bvs previous\b",
        ]
        return any(re.search(pat, q) for pat in comparison_patterns)

    def _is_hybrid_query(self, q: str) -> bool:
        """Detect queries needing both database records and knowledge base definitions."""
        has_record_request = any(k in q for k in ["records", "beneficiaries", "shops", "inventory", "who are", "list"])
        has_explanation_request = any(k in q for k in ["what does", "meaning", "explain", "why", "what is", "means", "define"])
        has_domain = any(k in q for k in ["duplicate", "claims", "flag", "phh", "aay", "beneficiary", "shop", "quota"])
        return has_record_request and has_explanation_request and has_domain

    def _is_definition_query(self, q: str) -> bool:
        """Detect questions asking for schema, field, flag, or policy definitions."""
        # Operational data questions (e.g. current stock quantities) are structured data queries, not dictionary definitions
        if any(k in q for k in ["current stock", "latest stock", "how much stock", "how many", "count", "show me", "list", "ranking"]):
            return False

        definition_patterns = [
            r"\bwhat (?:does|means?)\b",
            r"\bmeaning of\b",
            r"\bdefine\b",
            r"\bdefinition\b",
            r"\bstatutory quota\b",
            r"\bentitlement formula\b",
            r"\bhow is .* calculated\b",
            r"\bwhat do existing flags mean\b",
            r"\bwhat is (?:aay|phh|statutory quota|closing_stock|physical_stock|opening_stock|possible_duplicate|multiple_claims)\b",
        ]
        has_pattern = any(re.search(pat, q) for pat in definition_patterns)
        if not has_pattern:
            return False

        # Require PDS/RationRight domain relevance so generic "what is..." questions are not misrouted
        pds_terms = [
            "aay", "phh", "quota", "entitlement", "duplicate", "possible_duplicate",
            "multiple_claims", "review_reason", "closing_stock", "physical_stock",
            "opening_stock", "distributed", "manual_override", "inspection", "pwd",
            "dealer", "fps", "ration", "flag", "flags", "formula", "capacity",
            "commodity", "rice", "wheat", "beneficiary", "inventory", "unit",
        ]
        return any(re.search(r"\b" + re.escape(t) + r"\b", q) for t in pds_terms)

    def _handle_comparison(
        self,
        request: QueryRequest,
        question: str,
        target_id: Optional[str],
        dataset_name: Optional[str],
    ) -> RoutedQueryContext:
        """Execute historical snapshot comparison."""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT import_id, dataset_name FROM import_batches ORDER BY import_timestamp DESC")
            all_imports = cursor.fetchall()

        if len(all_imports) < 2:
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="COMPARISON_INSUFFICIENT_HISTORY",
                is_supported=False,
                sql_data={"error": "At least two weekly imports are required to perform a comparison."},
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        target = request.import_id or all_imports[0]["import_id"]
        baseline = request.baseline_import_id or all_imports[1]["import_id"]

        diff = compare_snapshots(baseline, target, db_path=self.db_path)
        return RoutedQueryContext(
            question=question,
            route_type=RouteType.STRUCTURED,
            intent="WEEKLY_SNAPSHOT_COMPARISON",
            sql_data=diff,
            is_supported=True,
            import_id_cited=target,
            dataset_name_cited=dataset_name,
        )

    def _handle_rag_definition(
        self,
        question: str,
        q_lower: str,
        target_id: Optional[str],
        dataset_name: Optional[str],
    ) -> RoutedQueryContext:
        """Execute RAG vector search for definitions, policies, or flags."""
        category = None
        if any(k in q_lower for k in ["aay", "phh", "quota", "entitlement"]):
            category = "welfare_policy"
        elif any(k in q_lower for k in ["duplicate", "multiple claim", "mismatch", "manual override", "flag"]):
            category = "system_flags"
        elif any(k in q_lower for k in ["schema", "field", "table", "capacity", "dealer"]):
            category = "schema_documentation"

        docs = self.retriever.query(question, top_k=3, category=category)
        return RoutedQueryContext(
            question=question,
            route_type=RouteType.RAG_DEFINITION,
            intent="DATA_DICTIONARY_DEFINITION",
            rag_context=docs,
            is_supported=True,
            import_id_cited=target_id,
            dataset_name_cited=dataset_name,
        )

    def _handle_hybrid(
        self,
        question: str,
        q_lower: str,
        target_id: Optional[str],
        dataset_name: Optional[str],
    ) -> RoutedQueryContext:
        """Execute both SQL record retrieval and RAG definition retrieval."""
        flag_type = "possible_duplicate" if "duplicate" in q_lower else ("multiple_claims" if "multiple" in q_lower else None)
        sql_records = get_flagged_beneficiaries(target_id, flag_type=flag_type, db_path=self.db_path)
        rag_docs = self.retriever.query(question, top_k=2)

        return RoutedQueryContext(
            question=question,
            route_type=RouteType.HYBRID,
            intent="HYBRID_RECORDS_AND_DEFINITION",
            sql_data={"flagged_records": sql_records, "total_count": len(sql_records)},
            rag_context=rag_docs,
            is_supported=True,
            import_id_cited=target_id,
            dataset_name_cited=dataset_name,
        )

    def _handle_structured(
        self,
        question: str,
        q_lower: str,
        target_id: Optional[str],
        dataset_name: Optional[str],
    ) -> RoutedQueryContext:
        """Route to specific safe SQL query functions based on query subject."""
        if not target_id:
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="NO_DATA_IMPORTED",
                is_supported=False,
                sql_data={"error": "No imported RationRight datasets found in database."},
            )

        # Require positive evidence of PDS domain or recognized contextual follow-up phrasing
        has_domain_term = any(
            re.search(r"\b" + re.escape(term) + r"\b", q_lower)
            for term in PDS_DOMAIN_KEYWORDS
        )
        is_contextual_follow_up = any(
            re.search(pat, q_lower)
            for pat in CONTEXTUAL_FOLLOW_UP_PATTERNS
        )

        if not has_domain_term and not is_contextual_follow_up:
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.UNSUPPORTED,
                intent="OUT_OF_DOMAIN",
                is_supported=False,
                sql_data=None,
                rag_context=None,
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        # 1. Duplicate Flags
        if "duplicate" in q_lower:
            records = get_flagged_beneficiaries(target_id, flag_type="possible_duplicate", db_path=self.db_path)
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="DUPLICATE_FLAGS_QUERY",
                sql_data={"records": records, "count": len(records)},
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        # 2. Multiple Claims
        if "multiple claim" in q_lower or "repeated transaction" in q_lower:
            records = get_flagged_beneficiaries(target_id, flag_type="multiple_claims", db_path=self.db_path)
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="MULTIPLE_CLAIMS_QUERY",
                sql_data={"records": records, "count": len(records)},
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        # 3. Shop Complaints / Audits
        if any(k in q_lower for k in ["complaint", "highest complaint", "most complaint"]):
            ranking = get_shop_complaints_ranking(target_id, limit=5, db_path=self.db_path)
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="SHOP_COMPLAINTS_RANKING",
                sql_data={"ranking": ranking},
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        # 4. Inventory / Stock Status
        if any(k in q_lower for k in ["inventory", "stock", "rice", "wheat", "shortage", "mismatch"]):
            commodity = "Rice" if "rice" in q_lower else ("Wheat" if "wheat" in q_lower else None)
            inv = get_inventory_status(target_id, commodity=commodity, db_path=self.db_path)
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="INVENTORY_STATUS_QUERY",
                sql_data={"inventory": inv, "total_records": len(inv)},
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        # 5. Beneficiary Count & Overview
        if any(k in q_lower for k in ["beneficiar", "how many", "total", "category", "phh", "aay"]):
            summary = get_beneficiaries_summary(target_id, db_path=self.db_path)
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="BENEFICIARIES_COUNT_QUERY",
                sql_data=summary,
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        # 6. Audits & Inspections
        if any(k in q_lower for k in ["audit", "inspection", "late opening"]):
            aud = get_audit_summary(target_id, db_path=self.db_path)
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="AUDIT_METRICS_QUERY",
                sql_data=aud,
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        # 7. Transactions
        if any(k in q_lower for k in ["transaction", "manual override"]):
            tx = get_transactions_summary(target_id, db_path=self.db_path)
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="TRANSACTIONS_SUMMARY_QUERY",
                sql_data=tx,
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        # 8. General Snapshot Summary / Status / Overview
        if any(k in q_lower for k in ["summary", "status", "overview", "report", "quota", "records"]):
            summary = get_beneficiaries_summary(target_id, db_path=self.db_path)
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="GENERAL_SNAPSHOT_OVERVIEW",
                sql_data=summary,
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        # 9. Contextual follow-up resolution
        if is_contextual_follow_up:
            summary = get_beneficiaries_summary(target_id, db_path=self.db_path)
            return RoutedQueryContext(
                question=question,
                route_type=RouteType.STRUCTURED,
                intent="CONTEXTUAL_FOLLOW_UP",
                sql_data={"notice": "Contextual follow-up resolved against active dataset.", "summary": summary},
                import_id_cited=target_id,
                dataset_name_cited=dataset_name,
            )

        # Fallback for questions without specific operational match
        return RoutedQueryContext(
            question=question,
            route_type=RouteType.UNSUPPORTED,
            intent="OUT_OF_DOMAIN",
            is_supported=False,
            sql_data=None,
            rag_context=None,
            import_id_cited=target_id,
            dataset_name_cited=dataset_name,
        )
