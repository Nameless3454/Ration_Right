import {
  ChatResponse,
  ImportBatchResponse,
  ImportBatchSummary,
  SnapshotMetricsResponse,
  SystemInfo,
} from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";

async function safeFetch(url: string, options?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, options);
  } catch (err: any) {
    if (err.name === "TypeError" || err.message?.includes("fetch")) {
      throw new Error(
        `Unable to connect to RationRight backend server at ${API_BASE_URL}. Please ensure the backend is running.`
      );
    }
    throw err;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson && errJson.detail) {
        errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export const apiService = {
  getBaseUrl(): string {
    return API_BASE_URL;
  },

  async getSystemInfo(): Promise<SystemInfo> {
    const res = await safeFetch(`${API_BASE_URL}/api/info`);
    return handleResponse<SystemInfo>(res);
  },

  async getImports(): Promise<ImportBatchSummary[]> {
    const res = await safeFetch(`${API_BASE_URL}/api/imports`);
    return handleResponse<ImportBatchSummary[]>(res);
  },

  async uploadDataset(file: File, datasetName?: string): Promise<ImportBatchResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (datasetName && datasetName.trim()) {
      formData.append("dataset_name", datasetName.trim());
    }

    const res = await safeFetch(`${API_BASE_URL}/api/import/upload`, {
      method: "POST",
      body: formData,
    });
    return handleResponse<ImportBatchResponse>(res);
  },

  async getSnapshotMetrics(
    importId: string = "latest",
    limit: number = 50,
    offset: number = 0
  ): Promise<SnapshotMetricsResponse> {
    const url = new URL(`${API_BASE_URL}/api/metrics/${encodeURIComponent(importId)}`);
    url.searchParams.set("limit", limit.toString());
    url.searchParams.set("offset", offset.toString());

    const res = await safeFetch(url.toString());
    return handleResponse<SnapshotMetricsResponse>(res);
  },

  async getInventoryRecords(
    importId: string = "latest",
    params?: { commodity?: string; pwd_id?: string; limit?: number; offset?: number }
  ): Promise<any> {
    const url = new URL(`${API_BASE_URL}/api/inventory/${encodeURIComponent(importId)}`);
    if (params?.commodity) url.searchParams.set("commodity", params.commodity);
    if (params?.pwd_id) url.searchParams.set("pwd_id", params.pwd_id);
    if (params?.limit !== undefined) url.searchParams.set("limit", params.limit.toString());
    if (params?.offset !== undefined) url.searchParams.set("offset", params.offset.toString());

    const res = await safeFetch(url.toString());
    return handleResponse<any>(res);
  },

  async sendChatMessage(
    question: string,
    importId?: string,
    baselineImportId?: string
  ): Promise<ChatResponse> {
    const res = await safeFetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        import_id: importId,
        baseline_import_id: baselineImportId,
      }),
    });
    return handleResponse<ChatResponse>(res);
  },

  async compareSnapshots(
    baselineImportId?: string,
    targetImportId?: string
  ): Promise<any> {
    const res = await safeFetch(`${API_BASE_URL}/api/compare`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        baseline_import_id: baselineImportId,
        target_import_id: targetImportId,
      }),
    });
    return handleResponse<any>(res);
  },

  async searchDictionary(
    query: string,
    topK: number = 3,
    category?: string
  ): Promise<any> {
    const res = await safeFetch(`${API_BASE_URL}/api/dictionary/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query,
        top_k: topK,
        category,
      }),
    });
    return handleResponse<any>(res);
  },
};
