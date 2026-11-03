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

