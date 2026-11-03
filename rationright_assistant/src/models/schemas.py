"""
Pydantic data models for imports, queries, and system entities.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ImportBatchResponse(BaseModel):
    import_id: str
    import_timestamp: str
    dataset_name: str
    total_records: int
    status: str
    source_type: str
    source_path: Optional[str] = None
    table_counts: Dict[str, int] = Field(default_factory=dict)


class ImportRequest(BaseModel):
    dataset_path: str = Field(..., description="Path to directory containing CSVs or a .json file")
    dataset_name: Optional[str] = Field(None, description="Optional custom name for this weekly dataset batch")


class ImportBatchSummary(BaseModel):
    import_id: str
    import_timestamp: str
    dataset_name: str
    total_records: int
    status: str
    source_type: str
    source_path: Optional[str] = None


class CompareRequest(BaseModel):
    baseline_import_id: Optional[str] = Field(
        None,
        description="Earlier historical import_id (e.g. last week). If omitted, previous batch is used.",
    )
    target_import_id: Optional[str] = Field(
        None,
        description="Later historical import_id (e.g. this week). If omitted, latest batch is used.",
    )


class SnapshotMetricsResponse(BaseModel):
    import_id: str
    dataset_name: str
    import_timestamp: str
    beneficiaries: Dict[str, Any]
    inventory: List[Dict[str, Any]]
    audits: Dict[str, Any]
    shop_complaints: List[Dict[str, Any]]
    transactions: Dict[str, Any]
    total_inventory_records: int = 0
    inventory_limit: int = 50
    inventory_offset: int = 0


class InventoryQueryResponse(BaseModel):
    import_id: str
    dataset_name: str
    total: int
    limit: int
    offset: int
    inventory: List[Dict[str, Any]]


class DictionarySearchRequest(BaseModel):
    query: str = Field(..., description="Semantic search query, e.g. 'what is possible_duplicate?'")
    top_k: int = Field(3, ge=1, le=10, description="Number of relevant chunks to retrieve")
    category: Optional[str] = Field(
        None,
        description="Optional category filter: welfare_policy, system_flags, schema_documentation, governance",
    )


class DictionarySearchResult(BaseModel):
    id: str
    title: str
    category: str
    content: str
    score: float


class RouteType(str, Enum):
    STRUCTURED = "STRUCTURED"
    RAG_DEFINITION = "RAG_DEFINITION"
    HYBRID = "HYBRID"
    UNSUPPORTED = "UNSUPPORTED"


class QueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question from official")
    import_id: Optional[str] = Field(
        None,
        description="Specific import_id to query. Defaults to latest imported dataset.",
    )
    baseline_import_id: Optional[str] = Field(
        None,
        description="Optional baseline import_id for historical comparisons.",
    )


class RoutedQueryContext(BaseModel):
    question: str
    route_type: RouteType
    intent: str
    sql_data: Optional[Any] = None
    rag_context: Optional[List[Dict[str, Any]]] = None
    is_supported: bool = True
    import_id_cited: Optional[str] = None
    dataset_name_cited: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    route_type: RouteType
    intent: str
    import_id_cited: Optional[str] = None
    dataset_name_cited: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    is_supported: bool = True
