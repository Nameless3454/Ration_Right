import React, { useState, useEffect } from "react";
import { Header } from "./components/Header";
import { OperationsDashboard } from "./components/OperationsDashboard";
import { DatasetUploadModal } from "./components/DatasetUploadModal";
import { FloatingChatbot } from "./components/chat/FloatingChatbot";
import { apiService } from "./services/api";
import {
  ChatMessage,
  ImportBatchResponse,
  ImportBatchSummary,
  SnapshotMetricsResponse,
} from "./types/api";

export const App: React.FC = () => {
  // System & Imports State
  const [imports, setImports] = useState<ImportBatchSummary[]>([]);
  const [selectedImportId, setSelectedImportId] = useState<string>("latest");
  const [systemStatus, setSystemStatus] = useState<"healthy" | "loading" | "error">("loading");

  // Metrics State
  const [metrics, setMetrics] = useState<SnapshotMetricsResponse | null>(null);
  const [isMetricsLoading, setIsMetricsLoading] = useState(true);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  // Modals & Chat State
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  // Initial Load: check system and fetch historical imports
  useEffect(() => {
    loadInitialData();
  }, []);

  // Fetch metrics whenever selected import changes
  useEffect(() => {
    loadMetrics(selectedImportId);
  }, [selectedImportId]);

  const loadInitialData = async () => {
    try {
      setSystemStatus("loading");
      const info = await apiService.getSystemInfo();
      setSystemStatus("healthy");

      const importList = await apiService.getImports();
      setImports(importList);
      if (importList.length > 0 && selectedImportId === "latest") {
        loadMetrics(importList[0].import_id);
      }
    } catch (err: any) {
      console.error("Initial load error:", err);
      setSystemStatus("error");
    }
  };

  const loadMetrics = async (importId: string) => {
    setIsMetricsLoading(true);
    setMetricsError(null);
    try {
      const data = await apiService.getSnapshotMetrics(importId, 50, 0);
      setMetrics(data);
    } catch (err: any) {
      console.error("Error loading metrics:", err);
      setMetricsError(err.message || "Failed to load snapshot metrics.");
    } finally {
      setIsMetricsLoading(false);
    }
  };

  // Upload Handlers
  const handleUploadSuccess = async (batch: ImportBatchResponse) => {
    // Refresh imports list
    const updatedImports = await apiService.getImports();
    setImports(updatedImports);
    setSelectedImportId(batch.import_id);
    await loadMetrics(batch.import_id);

    // Add proactive greeting in chat
    const systemNotice: ChatMessage = {
      id: `sys-${Date.now()}`,
      sender: "assistant",
      text: `### Dataset Batch Ingested Successfully\n\nBatch **${batch.dataset_name}** (\`${batch.import_id}\`) is now active.\n- Total Records: **${batch.total_records}**\n- Snapshot metrics updated in dashboard.\n\nYou can now inquire about beneficiaries, inventory ledger discrepancies, and shop audits for this import.`,
      timestamp: new Date().toISOString(),
      responseMeta: {
        import_id_cited: batch.import_id,
        dataset_name_cited: batch.dataset_name,
        route_type: "STRUCTURED",
        intent: "DATASET_UPLOAD_SUCCESS",
        is_supported: true,
      },
    };
    setChatMessages((prev) => [...prev, systemNotice]);
  };

  // Chat Handlers
  const handleSendMessage = async (question: string) => {
    if (!question.trim()) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: question,
      timestamp: new Date().toISOString(),
    };

    setChatMessages((prev) => [...prev, userMessage]);
    setIsChatLoading(true);
    setChatError(null);

    try {
      const targetId = selectedImportId === "latest" ? undefined : selectedImportId;
      const response = await apiService.sendChatMessage(question, targetId);

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: "assistant",
        text: response.answer,
        timestamp: new Date().toISOString(),
        responseMeta: {
          route_type: response.route_type,
          intent: response.intent,
          import_id_cited: response.import_id_cited,
          dataset_name_cited: response.dataset_name_cited,
          is_supported: response.is_supported,
          evidence: response.evidence,
        },
      };

      setChatMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      console.error("Chat error:", err);
      setChatError(err.message || "Failed to generate answer. Check backend connectivity.");
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleAskQuestionFromDashboard = (q: string) => {
    setIsChatOpen(true);
    handleSendMessage(q);
  };

  const selectedImportObj = imports.find((i) => i.import_id === selectedImportId) || imports[0];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Top Header & Snapshot Controls */}
      <Header
        imports={imports}
        selectedImportId={selectedImportId}
        onSelectImport={(id) => setSelectedImportId(id)}
        onOpenUpload={() => setIsUploadModalOpen(true)}
        onToggleChat={() => setIsChatOpen(!isChatOpen)}
        isChatOpen={isChatOpen}
        systemStatus={systemStatus}
      />

      {/* Main Operations Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <OperationsDashboard
          metrics={metrics}
          isLoading={isMetricsLoading}
          error={metricsError}
          onRefresh={() => loadMetrics(selectedImportId)}
          onAskQuestion={handleAskQuestionFromDashboard}
        />
      </main>

      {/* Floating Chatbot Assistant */}
      <FloatingChatbot
        isOpen={isChatOpen}
        onToggle={() => setIsChatOpen(!isChatOpen)}
        messages={chatMessages}
        isLoading={isChatLoading}
        error={chatError}
        onSendMessage={handleSendMessage}
        onClearHistory={() => setChatMessages([])}
        selectedImportId={selectedImportId}
        selectedImportName={selectedImportObj?.dataset_name || "Latest Snapshot"}
      />

      {/* Dataset Upload Modal */}
      <DatasetUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadSuccess={handleUploadSuccess}
      />
    </div>
  );
};

