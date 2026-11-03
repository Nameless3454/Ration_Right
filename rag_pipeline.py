"""
RationRight RAG (Retrieval-Augmented Generation) Pipeline.
Parses the October 2026 Ration Distribution Dataset into structured chunks,
extracts searchable representations with metadata, computes embeddings,
performs semantic vector search, and generates grounded answers.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

DATASET_PATH = "data/uploaded_dataset/rationright_demo_data.json"

class DocumentChunk:
    def __init__(
        self,
        chunk_id: str,
        text: str,
        entity_type: str,
        entity_id: str,
        metadata: Dict[str, Any],
        structured_data: Dict[str, Any]
    ):
        self.chunk_id = chunk_id
        self.text = text
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.metadata = metadata
        self.structured_data = structured_data
        self.tokens = self._tokenize(text)

    def _tokenize(self, text: str) -> List[str]:
        return [w.lower() for w in re.findall(r'\b[a-zA-Z0-9_\-]+\b', text)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "metadata": self.metadata,
            "structured_data": self.structured_data
        }

class RAGPipeline:
    def __init__(self, dataset_path: str = DATASET_PATH):
        self.dataset_path = dataset_path
        self.chunks: List[DocumentChunk] = []
        self.idf: Dict[str, float] = {}
        self.doc_vectors: List[Dict[str, float]] = []
        self._build_index()

    def _build_index(self):
        if not os.path.exists(self.dataset_path):
            return

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = data.get("metadata", {})
        period = meta.get("period", "2026-10")

        # 1. PWD Shops
        shops_dict = {}
        for shop in data.get("pwd_shops", []):
            shops_dict[shop["pwd_id"]] = shop
            text = (
                f"Fair Price Shop {shop['pwd_id']}: '{shop['shop_name']}' located in "
                f"{shop['district']}, {shop['state']}. Dealer ID: {shop['dealer_id']}. "
                f"Monthly distribution capacity: {shop['monthly_capacity_kg']} kg. "
                f"GPS Coordinates: ({shop.get('gps_lat')}, {shop.get('gps_lon')}). "
                f"Reporting Period: {period}."
            )
            self.chunks.append(DocumentChunk(
                chunk_id=f"SHOP-{shop['pwd_id']}",
                text=text,
                entity_type="pwd_shop",
                entity_id=shop["pwd_id"],
                metadata={
                    "source": "pwd_shops",
                    "reporting_period": period,
                    "district": shop["district"],
                    "state": shop["state"],
                    "pwd_id": shop["pwd_id"]
                },
                structured_data=shop
            ))

        # 2. Beneficiaries
        for b in data.get("beneficiaries", []):
            shop = shops_dict.get(b["pwd_id"], {})
            text = (
                f"Beneficiary {b['beneficiary_id']} (Ration Card: {b['ration_card_id']}): "
                f"Head of household: {b['head_name']}, Family size: {b['family_size']} members. "
                f"Category: {b['category']}. Assigned to Fair Price Shop: {b['pwd_id']} "
                f"({shop.get('shop_name', 'Local Shop')} in {shop.get('district', 'N/A')}, {shop.get('state', 'N/A')}). "
                f"Monthly entitlement: {b['monthly_entitlement_kg']} kg. "
                f"Collection status: {b['collection_status']}. Identity status: {b['identity_status']}. "
                f"Last collection date: {b.get('last_collection_date', 'N/A')}. "
                f"{'Review Reason: ' + b['review_reason'] if b.get('review_reason') else ''}"
            )
            self.chunks.append(DocumentChunk(
                chunk_id=f"BEN-{b['beneficiary_id']}",
                text=text,
                entity_type="beneficiary",
                entity_id=b["beneficiary_id"],
                metadata={
                    "source": "beneficiaries",
                    "reporting_period": period,
                    "category": b["category"],
                    "pwd_id": b["pwd_id"],
                    "identity_status": b["identity_status"],
                    "collection_status": b["collection_status"],
                    "district": shop.get("district", "N/A"),
                    "state": shop.get("state", "N/A")
                },
                structured_data=b
            ))

        # 3. Inventory
        for inv in data.get("inventory", []):
            shop = shops_dict.get(inv["pwd_id"], {})
            expected_close = inv["opening_stock_kg"] + inv["received_kg"] - inv["distributed_kg"]
            discrepancy = inv["physical_stock_kg"] - expected_close
            text = (
                f"Inventory Record {inv['inventory_id']} for Fair Price Shop {inv['pwd_id']} "
                f"({shop.get('shop_name', 'Local Shop')}, {shop.get('district', 'N/A')}): "
                f"Commodity: {inv['commodity']}, Month: {inv['month']}. "
                f"Opening stock: {inv['opening_stock_kg']} kg, Received quantity: {inv['received_kg']} kg, "
                f"Reported distribution: {inv['distributed_kg']} kg, Expected closing stock: {expected_close} kg, "
                f"Physically audited stock: {inv['physical_stock_kg']} kg. "
                f"Stock Discrepancy / Shortage: {discrepancy} kg ({'Deficit detected' if discrepancy < 0 else 'Balanced'})."
            )
            self.chunks.append(DocumentChunk(
                chunk_id=f"INV-{inv['inventory_id']}",
                text=text,
                entity_type="inventory",
                entity_id=inv["inventory_id"],
                metadata={
                    "source": "inventory",
                    "reporting_period": inv["month"],
                    "commodity": inv["commodity"],
                    "pwd_id": inv["pwd_id"],
                    "discrepancy_kg": discrepancy,
                    "district": shop.get("district", "N/A")
                },
                structured_data={**inv, "expected_closing_stock_kg": expected_close, "discrepancy_kg": discrepancy}
            ))

        # 4. Transactions
        for txn in data.get("transactions", []):
            shop = shops_dict.get(txn["pwd_id"], {})
            text = (
                f"Distribution Transaction {txn['transaction_id']}: Beneficiary {txn['beneficiary_id']} "
                f"collected {txn['quantity_kg']} kg of {txn['commodity']} on date {txn['date']} "
                f"at Fair Price Shop {txn['pwd_id']} ({shop.get('shop_name', 'Local Shop')}). "
                f"Authentication Channel: {txn['channel']}, Status: {txn['status']}."
            )
            self.chunks.append(DocumentChunk(
                chunk_id=f"TXN-{txn['transaction_id']}",
                text=text,
                entity_type="transaction",
                entity_id=txn["transaction_id"],
                metadata={
                    "source": "transactions",
                    "reporting_period": period,
                    "date": txn["date"],
                    "commodity": txn["commodity"],
                    "channel": txn["channel"],
                    "beneficiary_id": txn["beneficiary_id"],
                    "pwd_id": txn["pwd_id"]
                },
                structured_data=txn
            ))

        # 5. PWD Audits
        for aud in data.get("pwd_audits", []):
            shop = shops_dict.get(aud["pwd_id"], {})
            text = (
                f"Administrative Audit {aud['audit_id']} for Fair Price Shop {aud['pwd_id']} "
                f"({shop.get('shop_name', 'Local Shop')} in {shop.get('district', 'N/A')}): "
                f"Audit Period: {aud['period']}. Inspection Status: {aud['inspection_status'].upper()}. "
                f"Late opening days: {aud['late_opening_days']}, "
                f"Manual override transactions: {aud['manual_override_count']}, "
                f"Registered citizen complaints: {aud['complaints_count']}."
            )
            self.chunks.append(DocumentChunk(
                chunk_id=f"AUD-{aud['audit_id']}",
                text=text,
                entity_type="audit",
                entity_id=aud["audit_id"],
                metadata={
                    "source": "pwd_audits",
                    "reporting_period": aud["period"],
                    "inspection_status": aud["inspection_status"],
                    "pwd_id": aud["pwd_id"],
                    "district": shop.get("district", "N/A")
                },
                structured_data=aud
            ))

        # Compute TF-IDF Matrix for vector search
        total_docs = len(self.chunks)
        df: Dict[str, int] = {}
        for chunk in self.chunks:
            unique_terms = set(chunk.tokens)
            for t in unique_terms:
                df[t] = df.get(t, 0) + 1

        self.idf = {t: math.log((total_docs + 1) / (count + 1)) + 1.0 for t, count in df.items()}

        self.doc_vectors = []
        for chunk in self.chunks:
            vec: Dict[str, float] = {}
            for t in chunk.tokens:
                vec[t] = vec.get(t, 0.0) + 1.0
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            norm_vec = {t: (cnt / norm) * self.idf.get(t, 1.0) for t, cnt in vec.items()}
            self.doc_vectors.append(norm_vec)

    def search(self, query: str, top_k: int = 5, entity_type: Optional[str] = None) -> List[Tuple[DocumentChunk, float]]:
        """Vector similarity search against indexed dataset chunks."""
        q_tokens = [w.lower() for w in re.findall(r'\b[a-zA-Z0-9_\-]+\b', query)]
        if not q_tokens:
            return []

        q_vec: Dict[str, float] = {}
        for t in q_tokens:
            q_vec[t] = q_vec.get(t, 0.0) + 1.0
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        q_norm_vec = {t: (cnt / q_norm) * self.idf.get(t, 1.0) for t, cnt in q_vec.items()}

        scores = []
        for i, (chunk, d_vec) in enumerate(zip(self.chunks, self.doc_vectors)):
            if entity_type and chunk.entity_type != entity_type:
                continue

            score = 0.0
            for term, q_val in q_norm_vec.items():
                if term in d_vec:
                    score += q_val * d_vec[term]

            # Boost exact ID matches (e.g., PWD004, BEN019, INV003)
            for token in q_tokens:
                if token == chunk.entity_id.lower():
                    score += 1.5
                elif token in chunk.entity_id.lower():
                    score += 0.8

            if score > 0.05:
                scores.append((chunk, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def answer_query(self, query: str) -> Dict[str, Any]:
        """Retrieve relevant dataset chunks and generate a grounded answer."""
        results = self.search(query, top_k=5)
        if not results:
            return {
                "query": query,
                "answer": "No matching records found in the October 2026 Ration Distribution Dataset for your query. Try searching by shop ID (PWD001-PWD005), beneficiary ID (BEN001-BEN020), commodity (Rice, Wheat), or district (Ghaziabad, East Delhi, Noida).",
                "sources": [],
                "confidence": 0.0
            }

        top_chunks = [r[0] for r in results]
        sources = [
            {
                "chunk_id": c.chunk_id,
                "entity_type": c.entity_type,
                "entity_id": c.entity_id,
                "metadata": c.metadata,
                "preview": c.text[:120] + "..."
            }
            for c in top_chunks
        ]

        # Check if LLM narrative generation is available via agents/llm
        llm_response = None
        try:
            from agents.llm import _chat_completion, llm_enabled
            if llm_enabled():
                context_str = "\n".join([f"- {c.text}" for c in top_chunks])
                system_prompt = (
                    "You are RationRight's RAG Intelligence Assistant. Answer the user's question "
                    "using ONLY the verified facts provided in the context below from the October 2026 "
                    "Ration Distribution Dataset. State exact IDs, numbers, quantities in kg, dates, and locations. "
                    "If discrepancies or fraud alerts exist, mention them objectively. Never invent numbers."
                )
                user_msg = f"Context:\n{context_str}\n\nQuestion: {query}"
                llm_response = _chat_completion(
                    api_key=os.environ.get("OPENAI_API_KEY", ""),
                    base_url=os.environ.get("RATIONRIGHT_LLM_BASE_URL", "https://api.openai.com/v1"),
                    model=os.environ.get("RATIONRIGHT_LLM_MODEL", "gpt-4o-mini"),
                    system_prompt=system_prompt,
                    user_message=user_msg,
                    max_tokens=350,
                    timeout=12.0
                )
        except Exception:
            llm_response = None

        if llm_response and llm_response.strip():
            answer = llm_response.strip()
        else:
            # Deterministic, high-precision grounded answer synthesis
            answer_parts = []
            answer_parts.append(f"Based on the October 2026 Ration Distribution Dataset:")
            for chunk in top_chunks[:3]:
                answer_parts.append(f"• {chunk.text}")
            answer = "\n\n".join(answer_parts)

        return {
            "query": query,
            "answer": answer,
            "sources": sources,
            "confidence": round(min(results[0][1], 1.0), 2)
        }

# Global singleton instance
_rag_pipeline = None

def get_rag_pipeline() -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline

