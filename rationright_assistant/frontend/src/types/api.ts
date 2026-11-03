export type RouteType = "STRUCTURED" | "RAG_DEFINITION" | "HYBRID" | "UNSUPPORTED";

export interface ImportBatchSummary {
  import_id: string;
  import_timestamp: string;
  dataset_name: string;
  total_records: number;
  status: string;
  source_type: string;
  source_path?: string;
}

export interface ImportBatchResponse {
  import_id: string;
  import_timestamp: string;
  dataset_name: string;
  total_records: number;
  status: string;
  source_type: string;
  source_path?: string;
  table_counts: Record<string, number>;
}

export interface BeneficiarySummary {
  total_beneficiaries: number;
  phh_count: number;
  aay_count: number;
  verified_count: number;
  duplicate_flag_count: number;
  review_required_count: number;
  multiple_claims_count: number;
}

export interface InventoryItem {
  inventory_id: string;
  pwd_id: string;
  shop_name?: string;
  month: string;
  commodity: string;
  opening_stock_kg: number;
  received_kg: number;
  distributed_kg: number;
  closing_stock_kg: number;
  physical_stock_kg: number;
  unit: string;
  expected_closing_kg: number;
  physical_discrepancy_kg: number;
}

export interface AuditSummary {
  total_audits: number;
  total_complaints: number;
  avg_complaints_per_shop: number;
  late_openings_total: number;
  total_manual_overrides: number;
  passed_inspections: number;
  failed_inspections: number;
}

export interface ShopComplaintRanking {
  pwd_id: string;
  shop_name: string;
  district: string;
  state: string;
  complaints_count: number;
  late_opening_days: number;
  manual_override_count: number;
  inspection_status: string;
}

export interface TransactionsSummary {
  total_transactions: number;
  total_grain_distributed_kg?: number;
  total_distributed_kg?: number;
  biometric_count: number;
  manual_override_count: number;
  rice_distributed_kg?: number;
  wheat_distributed_kg?: number;
}

export interface SnapshotMetricsResponse {
  import_id: string;
  dataset_name: string;
  import_timestamp: string;
  beneficiaries: BeneficiarySummary;
  inventory: InventoryItem[];
  audits: AuditSummary;
  shop_complaints: ShopComplaintRanking[];
  transactions: TransactionsSummary;
  total_inventory_records: number;
  inventory_limit: number;
  inventory_offset: number;
}

export interface RagDocContext {
  id?: string;
  title?: string;
  category?: string;
  content?: string;
  score?: number;
}

export interface ChatResponse {
  answer: string;
  route_type: RouteType;
  intent: string;
  import_id_cited?: string;
  dataset_name_cited?: string;
  evidence: {
    sql_data?: any;
    rag_context?: RagDocContext[];
  };
  is_supported: boolean;
}

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  responseMeta?: {
    route_type?: RouteType;
    intent?: string;
    import_id_cited?: string;
    dataset_name_cited?: string;
    is_supported?: boolean;
    evidence?: {
      sql_data?: any;
      rag_context?: RagDocContext[];
    };
  };
}

export interface SystemInfo {
  service: string;
  version: string;
  data_directory: string;
  db_path: string;
  chroma_directory: string;
  llm_model: string;
  llm_configured: boolean;
}

