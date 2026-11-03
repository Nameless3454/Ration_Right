import { ChatResponse, ImportBatchSummary, SystemInfo } from "../types/assistant";

const API_BASE = (import.meta.env.VITE_ASSISTANT_API_URL || "http://localhost:8001").replace(/\/$/, "");

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 429) {
    const retryAfter = res.headers.get("Retry-After") || "60";
    throw new Error(`Rate limit exceeded. Please wait ${retryAfter} seconds before trying again.`);
  }

  if (!res.ok) {
    let errMsg = `Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      errMsg = errJson.detail || errJson.message || errJson.error || errMsg;
    } catch {
      // fallback
    }
    throw new Error(errMsg);
  }

  return res.json() as Promise<T>;
}

export const assistantApi = {
  /**
   * Send a question to the assistant chatbot endpoint.
   */
  async sendChatMessage(
    question: string,
    importId?: string,
    baselineImportId?: string
  ): Promise<ChatResponse> {
    const body: Record<string, any> = { question };
    if (importId) body.import_id = importId;
    if (baselineImportId) body.baseline_import_id = baselineImportId;

    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": "RATIONRIGHT_DEMO_KEY_2026",
      },
      body: JSON.stringify(body),
    });

    return handleResponse<ChatResponse>(res);
  },

  /**
   * Retrieve the list of imported weekly snapshots.
   */
  async getImportBatches(): Promise<ImportBatchSummary[]> {
    const res = await fetch(`${API_BASE}/api/imports`, {
      headers: {
        "x-api-key": "RATIONRIGHT_DEMO_KEY_2026",
      },
    });

    return handleResponse<ImportBatchSummary[]>(res);
  },

  /**
   * Retrieve backend system info and configuration status.
   */
  async getSystemInfo(): Promise<SystemInfo> {
    const res = await fetch(`${API_BASE}/api/system/info`, {
      headers: {
        "x-api-key": "RATIONRIGHT_DEMO_KEY_2026",
      },
    });

    return handleResponse<SystemInfo>(res);
  },
};

