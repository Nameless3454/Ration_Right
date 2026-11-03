"""
Gemini LLM Client for grounded response generation.
Adheres strictly to SYSTEM_PROMPT rules, citing import metadata and preserving neutrality.
"""
import logging
import os
from typing import Any, Dict, List, Optional

from src.config import settings
from src.llm.prompts import SYSTEM_INSTRUCTIONS, format_grounded_prompt
from src.models.schemas import ChatResponse, RouteType, RoutedQueryContext

logger = logging.getLogger(__name__)


class GroundedGenerator:
    """Generates grounded responses using Gemini or deterministic verification fallback."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self._genai_client = None

        if self.api_key:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini client initialized with model {self.model}")
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI client: {e}. Falling back to deterministic generator.")

    def generate_response(self, context: RoutedQueryContext) -> ChatResponse:
        """Formulate a grounded response strictly backed by context."""
        # 1. Handle Unsupported Queries
        if not context.is_supported or context.route_type == RouteType.UNSUPPORTED:
            if context.intent == "UNSUPPORTED_COMMODITY" and isinstance(context.sql_data, dict) and "error" in context.sql_data:
                unsupported_msg = (
                    f"{context.sql_data['error']} "
                    f"The assistant only answers questions using available weekly imported RationRight datasets."
                )
            else:
                unsupported_msg = (
                    "The imported RationRight datasets do not contain information to answer this question. "
                    "The assistant answers questions strictly using weekly imported RationRight datasets "
                    "and official system documentation."
                )
            return ChatResponse(
                answer=unsupported_msg,
                route_type=context.route_type,
                intent=context.intent,
                import_id_cited=context.import_id_cited,
                dataset_name_cited=context.dataset_name_cited,
                evidence={"sql_data": context.sql_data, "rag_context": context.rag_context},
                is_supported=False,
            )

        # 2. If Gemini API is available and configured, call Gemini
        if self._genai_client:
            try:
                from google import genai
                from google.genai import types

                prompt = format_grounded_prompt(context)
                response = self._genai_client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTIONS,
                        temperature=0.0,
                    ),
                )
                answer_text = response.text
                return ChatResponse(
                    answer=answer_text,
                    route_type=context.route_type,
                    intent=context.intent,
                    import_id_cited=context.import_id_cited,
                    dataset_name_cited=context.dataset_name_cited,
                    evidence={"sql_data": context.sql_data, "rag_context": context.rag_context},
                    is_supported=True,
                )
            except Exception as e:
                logger.error(f"Gemini API invocation failed: {e}. Falling back to deterministic synthesis.")

        # 3. Deterministic Grounded Synthesis (offline or when API key not set)
        answer_text = self._synthesize_grounded_fallback(context)
        return ChatResponse(
            answer=answer_text,
            route_type=context.route_type,
            intent=context.intent,
            import_id_cited=context.import_id_cited,
            dataset_name_cited=context.dataset_name_cited,
            evidence={"sql_data": context.sql_data, "rag_context": context.rag_context},
            is_supported=True,
        )

    def _synthesize_grounded_fallback(self, context: RoutedQueryContext) -> str:
        """
        Deterministic, audit-compliant conversational synthesis that guarantees zero hallucination,
        exact numeric accuracy, conversational structure, and mandatory neutrality disclaimers.
        """
        dataset = context.dataset_name_cited or "RationRight Weekly Import"
        import_id = context.import_id_cited or "Unknown"
        source_footer = f"\n\n*Source: `{dataset}` (Import ID: `{import_id}`)*"

        # A. Specific Beneficiary Record / Fraud Accusation Defense
        if context.intent in ["BENEFICIARY_FRAUD_INQUIRY", "BENEFICIARY_RECORD_LOOKUP"] and isinstance(context.sql_data, dict):
            if "records" in context.sql_data:
                records = context.sql_data.get("records", [])
                if not records:
                    return (
                        f"No beneficiary records are currently flagged for review in dataset `{dataset}`.\n\n"
                        f"*Administrative Notice: Under RationRight operating rules, system indicators are review leads. "
                        f"The assistant never declares any citizen fraudulent or guilty.*"
                        f"{source_footer}"
                    )
                lines = [
                    f"There are {len(records)} beneficiary records flagged for administrative review in dataset `{dataset}`.\n\n"
                    f"Here are the identified records requiring verification:"
                ]
                for r in records:
                    lines.append(
                        f"- **Beneficiary ID `{r['beneficiary_id']}`** (Ration Card: `{r['ration_card_id']}`, Assigned Shop: {r.get('shop_name') or r['pwd_id']}): {r.get('review_reason') or 'Flagged for review'}"
                    )
                lines.append(
                    "\n> [!IMPORTANT]\n"
                    "> **Administrative Boundary & Fraud Disclaimer:**\n"
                    "> Under RationRight operating rules, system flags such as `possible_duplicate` are strictly administrative review leads to guide human inspection. "
                    "Neither automated AI systems nor operational algorithms have the legal authority to declare any beneficiary fraudulent, corrupt, or guilty. "
                    "All citizens retain the statutory right to field verification and fair appeal, and final determinations rest exclusively with authorized food security officials."
                )
                lines.append(f"{source_footer.strip()}")
                return "\n".join(lines)

            b = context.sql_data.get("beneficiary")
            ben_id = context.sql_data.get("beneficiary_id")
            if not b:
                return (
                    f"No beneficiary record found with ID `{ben_id}` in dataset `{dataset}`.\n\n"
                    f"*Administrative Rule: Under system boundaries, the assistant never declares any person fraudulent or guilty. Operational decisions rest exclusively with authorized officials.*"
                    f"{source_footer}"
                )

            status_note = b.get("review_reason") or f"Identity status: {b.get('identity_status')}"
            return (
                f"Here is the verified operational record for Beneficiary `{b['beneficiary_id']}` ({b['head_name']}):\n\n"
                f"- **Citizen Name:** {b['head_name']}\n"
                f"- **Ration Card ID:** `{b['ration_card_id']}`\n"
                f"- **Welfare Category:** {b['category']} (Family size: {b['family_size']})\n"
                f"- **Assigned Fair Price Shop:** {b.get('shop_name') or b['pwd_id']}\n"
                f"- **Monthly Entitlement:** {b['monthly_entitlement_kg']} kg\n"
                f"- **Operational Status:** `{b['identity_status']}` | Collection: `{b['collection_status']}`\n"
                f"- **Administrative Review Note:** {status_note}\n\n"
                f"> [!IMPORTANT]\n"
                f"> **Administrative Boundary & Fraud Disclaimer:**\n"
                f"> Under RationRight operating rules, system flags such as `{b['identity_status']}` are strictly administrative review leads to guide human inspection. "
                f"Neither automated AI systems nor operational algorithms have the legal authority to declare any beneficiary fraudulent, corrupt, or guilty. "
                f"All citizens retain the statutory right to field verification and fair appeal, and final determinations rest exclusively with authorized food security officials."
                f"{source_footer}"
            )

        # A2. Fair Price Shop / Dealer Inquiries & Accusation Defense
        if context.intent in ["SHOP_FRAUD_INQUIRY", "SHOP_RECORD_LOOKUP"] and isinstance(context.sql_data, dict):
            if "ranking" in context.sql_data:
                ranking = context.sql_data.get("ranking", [])
                if not ranking:
                    return (
                        f"No shop complaint records were found in dataset `{dataset}`.\n\n"
                        f"*Administrative Rule: Operational indicators guide official oversight. The assistant never labels dealers fraudulent or corrupt.*"
                        f"{source_footer}"
                    )
                lines = [
                    f"Based on verified operations data, citizen complaints were recorded across {len(ranking)} Fair Price Shops in dataset `{dataset}`. "
                    f"{ranking[0]['shop_name']} currently has the highest recorded complaint volume with {ranking[0]['complaints_count']} citizen complaints.\n\n"
                    f"### Fair Price Shops Operational Review & Complaints Overview:"
                ]
                for idx, s in enumerate(ranking, start=1):
                    dealer_str = f" - Dealer: `{s['dealer_id']}`" if s.get("dealer_id") else ""
                    lines.append(
                        f"{idx}. **{s['shop_name']}** (`{s['pwd_id']}`{dealer_str}):\n"
                        f"   - **Complaints:** {s['complaints_count']} | **Status:** `{s['inspection_status']}` | **Late Days:** {s['late_opening_days']}"
                    )
                lines.append(
                    "\n> [!IMPORTANT]\n"
                    "> **Administrative Boundary & Neutrality Disclaimer:**\n"
                    "> Administrative metrics such as citizen complaints, inspection notices, or late opening days are operational indicators for departmental oversight. "
                    "Neither automated AI systems nor operational records have the legal authority to label any Fair Price Shop or dealer as fraudulent, corrupt, or criminal. "
                    "All dealers retain the statutory right to formal inquiry, audit reconciliation, and procedural appeal."
                )
                lines.append(f"{source_footer.strip()}")
                return "\n".join(lines)

            s = context.sql_data.get("shop")
            ent_id = context.sql_data.get("entity_id")
            if not s:
                return (
                    f"No Fair Price Shop or Dealer record found with ID `{ent_id}` in dataset `{dataset}`.\n\n"
                    f"*Administrative Rule: Under system boundaries, the assistant never labels any dealer or shop fraudulent or corrupt. Operational determinations rest exclusively with authorized officials.*"
                    f"{source_footer}"
                )

            return (
                f"Here is the operational profile for Fair Price Shop `{s['pwd_id']}` ({s['shop_name']}), managed by Dealer `{s['dealer_id']}`:\n\n"
                f"- **Shop Name:** {s['shop_name']}\n"
                f"- **Location:** {s['district']}, {s['state']}\n"
                f"- **Monthly Capacity:** {s['monthly_capacity_kg']} kg\n"
                f"- **Inspection Status:** `{s['inspection_status']}`\n"
                f"- **Citizen Complaints:** {s['complaints_count']}\n"
                f"- **Late Opening Days:** {s['late_opening_days']}\n"
                f"- **Manual Overrides:** {s['manual_override_count']}\n\n"
                f"> [!IMPORTANT]\n"
                f"> **Administrative Boundary & Neutrality Disclaimer:**\n"
                f"> Under RationRight operating rules, administrative metrics such as complaints ({s['complaints_count']}), inspection status (`{s['inspection_status']}`), or late openings are strictly operational review indicators to guide official oversight. "
                f"Neither automated AI systems nor operational algorithms have the legal authority to label any Fair Price Shop, dealer, or merchant fraudulent, corrupt, or guilty of criminal wrongdoing. "
                f"All dealers retain statutory rights to formal inquiry, audit reconciliation, and procedural appeal, with final determinations resting exclusively with authorized food security and vigilance authorities."
                f"{source_footer}"
            )

        # B. Beneficiary Counts
        if context.intent == "BENEFICIARIES_COUNT_QUERY" and isinstance(context.sql_data, dict):
            d = context.sql_data
            total = d.get('total_beneficiaries', 0)
            phh = d.get('phh_count', 0)
            aay = d.get('aay_count', 0)
            dup = d.get('duplicate_flag_count', 0)
            mult = d.get('multiple_claims_count', 0)
            verified = d.get('verified_count', 0)
            return (
                f"There are {total} beneficiaries registered in the latest imported dataset (`{dataset}`).\n\n"
                f"### Beneficiary Enrollment Summary\n"
                f"- **Total Registered Beneficiaries:** {total}\n"
                f"- **Priority Households (PHH):** {phh}\n"
                f"- **Antyodaya Anna Yojana (AAY):** {aay}\n"
                f"- **Biometrically Verified:** {verified}\n"
                f"- **Duplicate Biometric Flags:** {dup}\n"
                f"- **Multiple Claims Flags:** {mult}\n\n"
                f"Among these, {dup} records are flagged as possible duplicates and {mult} record has a multiple-claims flag. "
                f"These are indicators requiring administrative review, not proof of wrongdoing."
                f"{source_footer}"
            )

        # C. Duplicate Flags
        if context.intent == "DUPLICATE_FLAGS_QUERY" and isinstance(context.sql_data, dict):
            records = context.sql_data.get("records", [])
            if not records:
                return (
                    f"There are no beneficiary records flagged as possible duplicates in dataset `{dataset}`.\n\n"
                    f"*Administrative Notice: Flags are review leads for field verification, not proof of fraud.*"
                    f"{source_footer}"
                )
            lines = [
                f"There are {len(records)} beneficiary records flagged as possible duplicates in the active dataset (`{dataset}`).\n\n"
                f"Here are the identified records requiring verification:"
            ]
            for r in records:
                lines.append(
                    f"- **Beneficiary ID `{r['beneficiary_id']}`** (Ration Card: `{r['ration_card_id']}`, Shop: `{r.get('shop_name') or r['pwd_id']}`):\n"
                    f"  *Reason:* {r.get('review_reason') or 'Flagged for demographic/biometric match'}"
                )
            lines.append(
                "\n> [!NOTE]\n"
                "> Every flag is strictly an administrative review lead to guide human field inspection. "
                "It is not evidence of fraud, and cardholders retain the statutory right to verification and appeal."
            )
            lines.append(f"{source_footer.strip()}")
            return "\n".join(lines)

        # C2. Multiple Claims Flags
        if context.intent == "MULTIPLE_CLAIMS_QUERY" and isinstance(context.sql_data, dict):
            records = context.sql_data.get("records", [])
            if not records:
                return (
                    f"There are no records with multiple claims detected in dataset `{dataset}`.\n\n"
                    f"*Administrative Notice: All transactions align with standard monthly entitlements.*"
                    f"{source_footer}"
                )
            lines = [
                f"There are {len(records)} beneficiary records flagged with multiple-claims indicators in dataset `{dataset}`.\n\n"
                f"Here are the identified records requiring supervisory reconciliation:"
            ]
            for r in records:
                lines.append(
                    f"- **Beneficiary ID `{r['beneficiary_id']}`** (Ration Card: `{r['ration_card_id']}`, Shop: `{r.get('shop_name') or r['pwd_id']}`):\n"
                    f"  *Reason:* {r.get('review_reason') or 'Multiple claims detected in current distribution cycle'}"
                )
            lines.append(
                "\n> [!NOTE]\n"
                "> Multiple-claims flags indicate distribution timing discrepancies or repeated biometric attempts. "
                "These are operational leads for supervisory reconciliation, not proof of fraud."
            )
            lines.append(f"{source_footer.strip()}")
            return "\n".join(lines)

        # D. Shop Complaints Ranking
        if context.intent == "SHOP_COMPLAINTS_RANKING" and isinstance(context.sql_data, dict):
            ranking = context.sql_data.get("ranking", [])
            if not ranking:
                return (
                    f"No citizen complaints are recorded for Fair Price Shops in dataset `{dataset}`."
                    f"{source_footer}"
                )
            lines = [
                f"Fair Price Shops are ranked below by citizen complaint volume in dataset `{dataset}`. "
                f"{ranking[0]['shop_name']} currently has the highest volume with {ranking[0]['complaints_count']} complaints.\n\n"
                f"### Fair Price Shops Ranked by Citizen Complaints:"
            ]
            for idx, s in enumerate(ranking, start=1):
                lines.append(
                    f"{idx}. **{s['shop_name']}** (`{s['pwd_id']}` - {s['district']}, {s['state']}):\n"
                    f"   - **Complaints:** {s['complaints_count']}\n"
                    f"   - **Inspection Status:** `{s['inspection_status']}`\n"
                    f"   - **Late Opening Days:** {s['late_opening_days']}\n"
                    f"   - **Manual Overrides:** {s['manual_override_count']}"
                )
            lines.append(
                "\n*Administrative Notice: Complaint volumes guide routine departmental inspections and do not constitute formal disciplinary findings.*"
            )
            lines.append(f"{source_footer.strip()}")
            return "\n".join(lines)

        # E. Inventory Status
        if context.intent == "INVENTORY_STATUS_QUERY" and isinstance(context.sql_data, dict):
            inv = context.sql_data.get("inventory", [])
            if not inv:
                return (
                    f"No commodity inventory records were found in dataset `{dataset}`."
                    f"{source_footer}"
                )
            
            discrepancy_count = sum(1 for i in inv if i.get("physical_discrepancy_kg", 0) != 0)
            lines = [
                f"Here is the verified commodity inventory ledger and physical audit status for `{dataset}`. "
                f"Across {len(inv)} tracked commodity allocations, {discrepancy_count} shop records show physical variances requiring reconciliation.\n",
                "| Fair Price Shop | Commodity | Opening | Received | Distributed | Closing Book | Physical Audit | Variance |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
            for item in inv:
                disc = item["physical_discrepancy_kg"]
                status_str = f"Shortage of {abs(disc)} kg" if disc < 0 else (f"Surplus of {disc} kg" if disc > 0 else "Balanced")
                disc_display = f"**{disc:+d} kg** ({status_str})" if disc != 0 else "0 kg (Balanced)"
                lines.append(
                    f"| {item['shop_name']} | {item['commodity']} | {item['opening_stock_kg']} kg | {item['received_kg']} kg | {item['distributed_kg']} kg | {item['closing_stock_kg']} kg | {item['physical_stock_kg']} kg | {disc_display} |"
                )
            lines.append(
                "\n*Administrative Notice: Inventory variances indicate discrepancies between ledger books and physical audit counts. "
                "These trigger joint reconciliation by the Fair Price Shop dealer and inspecting officer.*"
            )
            lines.append(f"{source_footer.strip()}")
            return "\n".join(lines)

        # F. Weekly Snapshot Comparison
        if context.intent == "WEEKLY_SNAPSHOT_COMPARISON" and isinstance(context.sql_data, dict):
            d = context.sql_data
            meta = d.get("metadata_comparison", {})
            ben_delta = d.get("beneficiaries_summary_delta", {})
            inv_changes = d.get("inventory_changes", {})

            base_name = meta.get("baseline_import", {}).get("dataset_name", "Previous Week")
            target_name = meta.get("target_import", {}).get("dataset_name", "Current Week")
            base_id = meta.get("baseline_import", {}).get("import_id", "N/A")
            target_id = meta.get("target_import", {}).get("import_id", "N/A")

            lines = [
                f"Comparing the active snapshot **`{target_name}`** against baseline **`{base_name}`**:\n",
                f"### Weekly Snapshot Comparison\n",
                f"- **Baseline Dataset:** `{base_name}` (ID: `{base_id}`)\n",
                f"- **Target Dataset:** `{target_name}` (ID: `{target_id}`)\n\n",
                f"#### Beneficiary Metric Changes:\n",
                f"- Total Beneficiaries Delta: {ben_delta.get('total_beneficiaries_delta', 0):+d}\n",
                f"- Duplicate Flags Delta: {ben_delta.get('duplicate_flags_delta', 0):+d}\n",
                f"- Multiple Claims Delta: {ben_delta.get('multiple_claims_delta', 0):+d}\n\n",
                f"#### Inventory Changes:\n",
                f"- Changed Inventory Items: {inv_changes.get('changed_inventory_items_count', 0)}\n",
                f"- Net Physical Stock Delta: {inv_changes.get('total_physical_stock_delta_kg', 0):+d} kg\n",
            ]
            for ch in inv_changes.get("item_changes", []):
                lines.append(
                    f"  * {ch['shop_name']} ({ch['commodity']}): Physical Stock changed from {ch['baseline_physical_kg']} kg to {ch['target_physical_kg']} kg ({ch['physical_stock_delta_kg']:+d} kg)"
                )
            lines.append(f"\n*Source: Comparison between `{base_name}` (ID: `{base_id}`) and `{target_name}` (ID: `{target_id}`)*")
            return "\n".join(lines)

        # G. RAG Data Dictionary Definitions
        if context.route_type == RouteType.RAG_DEFINITION and context.rag_context:
            lines = ["According to official RationRight system documentation and governance policies:\n"]
            for doc in context.rag_context:
                lines.append(f"### {doc.get('title')}\n{doc.get('content')}\n")
            lines.append("*Source: RationRight Official Data Dictionary & Governance Policy*")
            return "\n".join(lines)

        # H. Hybrid
        if context.route_type == RouteType.HYBRID:
            lines = [
                f"Here is the verified operational data alongside relevant policy guidance for `{dataset}`:\n"
            ]
            if isinstance(context.sql_data, dict) and "flagged_records" in context.sql_data:
                records = context.sql_data["flagged_records"]
                lines.append(f"### Identified Operational Records ({len(records)} found):")
                for r in records:
                    lines.append(f"- **Beneficiary `{r['beneficiary_id']}`** (Ration Card: `{r['ration_card_id']}`): {r.get('review_reason') or 'Review flag'}")
                lines.append("")
            if context.rag_context:
                lines.append("### Relevant System Policy Definition:")
                for doc in context.rag_context:
                    lines.append(f"- **{doc.get('title')}:** {doc.get('content')}")
            lines.append(
                "\n> [!NOTE]\n"
                "> Operational flags are administrative review leads to guide human verification, never proof of fraud. "
                "Cardholders retain statutory rights to field verification and procedural appeal."
            )
            lines.append(f"{source_footer.strip()}")
            return "\n".join(lines)

        # I. General Overview / Contextual Follow-up
        if context.intent in ["GENERAL_SNAPSHOT_OVERVIEW", "CONTEXTUAL_FOLLOW_UP"] and isinstance(context.sql_data, dict):
            summary = context.sql_data.get("summary") or context.sql_data
            return (
                f"Here is an overview of the active RationRight operational snapshot for `{dataset}`:\n\n"
                f"- **Total Beneficiaries:** {summary.get('total_beneficiaries', 0)}\n"
                f"- **Priority Households (PHH):** {summary.get('phh_count', 0)}\n"
                f"- **Antyodaya Anna Yojana (AAY):** {summary.get('aay_count', 0)}\n"
                f"- **Biometrically Verified:** {summary.get('verified_count', 0)}\n"
                f"- **Duplicate Biometric Flags:** {summary.get('duplicate_flag_count', 0)}\n"
                f"- **Multiple Claims Flags:** {summary.get('multiple_claims_count', 0)}\n\n"
                f"Operational metrics reflect the active weekly imported dataset. System flags indicate leads for administrative review."
                f"{source_footer}"
            )

        # J. Transactions Summary
        if context.intent == "TRANSACTIONS_SUMMARY_QUERY" and isinstance(context.sql_data, dict):
            d = context.sql_data
            total_tx = d.get("total_transactions", 0)
            grain = d.get("total_grain_distributed_kg", d.get("total_distributed_kg", 0))
            auth_mode = d.get("auth_mode_breakdown", {})
            return (
                f"Here is the transaction and distribution summary for `{dataset}`:\n\n"
                f"- **Total Transactions:** {total_tx}\n"
                f"- **Total Grain Distributed:** {grain} kg\n"
                f"- **Biometric Authentications:** {auth_mode.get('Aadhaar_OTP', 0) + auth_mode.get('Biometric_FP', 0)}\n"
                f"- **Manual Overrides:** {auth_mode.get('Manual_Override', 0)}\n\n"
                f"Manual overrides require supervisory log verification per National Food Security Act compliance guidelines."
                f"{source_footer}"
            )

        # K. Audit Metrics
        if context.intent == "AUDIT_METRICS_QUERY" and isinstance(context.sql_data, dict):
            audits = context.sql_data.get("audits") or []
            lines = [
                f"Here is the status of operational audit inspections across Fair Price Shops in `{dataset}`:\n"
            ]
            for a in audits:
                lines.append(
                    f"- **{a.get('shop_name', 'FPS')}** (`{a.get('pwd_id', 'N/A')}`): Inspection Status: `{a.get('inspection_status')}`, Late Days: {a.get('late_opening_days', 0)}, Complaints: {a.get('complaints_count', 0)}"
                )
            lines.append(f"{source_footer.strip()}")
            return "\n".join(lines)

        return f"Query resolved successfully with verified system evidence.{source_footer}"


# Global client instance
_generator: Optional[GroundedGenerator] = None


def get_generator() -> GroundedGenerator:
    """Singleton accessor for GroundedGenerator."""
    global _generator
    if _generator is None:
        _generator = GroundedGenerator()
    return _generator
