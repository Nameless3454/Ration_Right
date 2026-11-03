"""
Prompt templates and context assemblers for grounded response generation with Gemini.
Enforces RationRight data boundaries, mandatory citations, and administrative neutrality.
"""
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from src.models.schemas import RoutedQueryContext, RouteType

SYSTEM_INSTRUCTIONS = """You are the official conversational AI Operations Assistant for RationRight, India's national Public Distribution System (PDS) operational platform.

STRICT OPERATING RULES:
1. Grounded Data-Only: Answer strictly and exclusively using the provided Verified SQL Evidence and RAG Context. NEVER use external websites or general knowledge. If the provided data does not contain the answer, say: "The imported RationRight datasets do not contain information to answer this question."
2. Conversational & Professional Tone: Communicate like a knowledgeable, professional government operations analyst. Provide a direct natural language answer first, followed by a concise explanation and key findings. Avoid dumping raw database records or excessive technical IDs.
3. Citations: Cite the dataset name and Import ID at the end of your response as a source attribution.
4. Administrative Neutrality: NEVER declare or state that any beneficiary, Fair Price Shop, or dealer is "fraudulent", "corrupt", "criminal", or "guilty". Flags like possible_duplicate, multiple_claims, complaints, and inspection notices are strictly review indicators for human verification only, never proof of confirmed wrongdoing.
5. Presume Good Faith: Preserve the official's authority to make final decisions.
6. Numerical Precision: State verified figures precisely as shown in the SQL evidence; never hallucinate or alter numbers.
"""


def format_grounded_prompt(context: RoutedQueryContext) -> str:
    """Format the full context prompt for Gemini."""
    prompt_parts: List[str] = [
        f"USER QUESTION: {context.question}\n",
        f"ROUTING INTENT: {context.intent} (Route: {context.route_type.value})\n",
    ]

    # Citation Metadata
    if context.import_id_cited:
        prompt_parts.append(
            f"DATASET CITATION:\n"
            f"- Import ID: {context.import_id_cited}\n"
            f"- Dataset Name: {context.dataset_name_cited or 'RationRight Weekly Import'}\n"
        )

    # SQL Evidence
    if context.sql_data:
        prompt_parts.append(
            "VERIFIED DATABASE EVIDENCE (SQL Query Output):\n"
            f"```json\n{json.dumps(context.sql_data, indent=2)}\n```\n"
        )

    # RAG Context
    if context.rag_context:
        prompt_parts.append("RETRIEVED DATA DICTIONARY & POLICY CONTEXT (ChromaDB):\n")
        for idx, doc in enumerate(context.rag_context, start=1):
            prompt_parts.append(
                f"[{idx}] Title: {doc.get('title')}\n"
                f"Category: {doc.get('category')}\n"
                f"Content: {doc.get('content')}\n"
            )
        prompt_parts.append("")

    prompt_parts.append(
        "INSTRUCTIONS FOR RESPONSE:\n"
        "- Synthesize a conversational, professional administrative briefing.\n"
        "- Give the direct answer first, then provide a concise explanation of key findings.\n"
        "- State verified figures precisely as shown in the SQL evidence without dumping raw database rows.\n"
        "- Cite the Import ID and Dataset Name as a source footnote at the bottom.\n"
        "- Maintain strict official neutrality without accusing any citizen, shop, or dealer of fraud."
    )

    return "\n".join(prompt_parts)

