import React, { useState, useEffect } from "react";
import {
  X,
  Minimize2,
  Maximize2,
  RotateCcw,
  Bot,
  Database,
} from "lucide-react";
import { ChatMessage, ImportBatchSummary } from "../../types/assistant";
import { assistantApi } from "../../services/assistantApi";
import { ChatHistory } from "./ChatHistory";
import { ChatInput } from "./ChatInput";

interface FloatingChatbotProps {
  activeRoute?: string;
}

export const FloatingChatbot: React.FC<FloatingChatbotProps> = ({ activeRoute = "overview" }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [importBatches, setImportBatches] = useState<ImportBatchSummary[]>([]);
  const [selectedImportId, setSelectedImportId] = useState<string>("");
  const [selectedImportName, setSelectedImportName] = useState<string>("Latest Snapshot");

  // Fetch available snapshots on load
  useEffect(() => {
    const fetchImports = async () => {
      try {
        const batches = await assistantApi.getImportBatches();
        if (batches && batches.length > 0) {
          setImportBatches(batches);
          setSelectedImportId(batches[0].import_id);
          setSelectedImportName(batches[0].dataset_name);
        }
      } catch (err: any) {
        console.warn("Could not fetch import batches for assistant:", err?.message);
      }
    };
    fetchImports();
  }, []);

  const handleSendMessage = async (queryText: string) => {
    if (!queryText.trim() || isLoading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: queryText.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setError(null);

    try {
      const res = await assistantApi.sendChatMessage(
        queryText.trim(),
        selectedImportId || undefined
      );

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: "assistant",
        text: res.answer,
        timestamp: new Date().toISOString(),
        responseMeta: {
          route_type: res.route_type,
          intent: res.intent,
          import_id_cited: res.import_id_cited,
          dataset_name_cited: res.dataset_name_cited,
          is_supported: res.is_supported,
          evidence: res.evidence,
        },
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      console.error("Chat message error:", err);
      setError(err?.message || "Failed to reach the RationRight Assistant backend.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearHistory = () => {
    setMessages([]);
    setError(null);
  };

  const handleSelectSnapshot = (batch: ImportBatchSummary) => {
    setSelectedImportId(batch.import_id);
    setSelectedImportName(batch.dataset_name);
  };

  return (
    <>
      {/* Floating Trigger Button (when closed) */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          aria-label="Open RationRight AI Assistant"
          className="fixed bottom-6 right-6 z-[1050] flex items-center gap-2.5 px-4 py-3 bg-gov-900 hover:bg-gov-800 text-white rounded-full shadow-2xl border border-gov-700/80 hover:scale-105 transition duration-150 group"
        >
          <div className="relative">
            <Bot className="w-5 h-5 text-india-saffron" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 ring-2 ring-gov-900" />
          </div>
          <span className="text-xs font-bold tracking-wide">RationRight AI Assistant</span>
        </button>
      )}

      {/* Floating Chat Modal Panel */}
      {isOpen && (
        <div
          className={`fixed z-[1050] transition-all duration-200 shadow-2xl flex flex-col bg-slate-50 border border-slate-300 rounded-2xl overflow-hidden ${
            isMinimized
              ? "bottom-6 right-6 w-80 h-14"
              : isExpanded
              ? "bottom-6 right-6 w-[94vw] sm:w-[680px] h-[85vh] max-h-[850px]"
              : "bottom-6 right-6 w-[94vw] sm:w-[460px] h-[640px] max-h-[90vh]"
          }`}
        >
          {/* Header Bar */}
          <div className="px-4 py-3 bg-gov-900 text-white border-b border-gov-800 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-gov-800 border border-gov-700 flex items-center justify-center">
                <Bot className="w-4 h-4 text-india-saffron" />
              </div>
              <div>
                <h3 className="text-xs font-bold flex items-center gap-1.5 text-white">
                  RationRight AI Assistant
                </h3>
                <div className="flex items-center gap-1.5 text-[10px] text-gov-300">
                  <span className="px-1.5 py-0.2 rounded bg-gov-800 border border-gov-700/60 uppercase text-[9px] font-mono tracking-wider text-gov-300">
                    {activeRoute}
                  </span>
                  {importBatches.length > 1 ? (
                    <div className="relative flex items-center gap-1">
                      <Database className="w-3 h-3 text-gov-400 shrink-0" />
                      <select
                        value={selectedImportId}
                        onChange={(e) => {
                          const found = importBatches.find((b) => b.import_id === e.target.value);
                          if (found) handleSelectSnapshot(found);
                        }}
                        className="bg-transparent text-gov-200 hover:text-white border-none focus:outline-none cursor-pointer truncate max-w-[140px]"
                      >
                        {importBatches.map((b) => (
                          <option key={b.import_id} value={b.import_id} className="bg-gov-900 text-white">
                            {b.dataset_name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : (
                    <span className="font-mono truncate max-w-[140px]">
                      {selectedImportName}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-1 text-gov-300">
              {/* Clear conversation */}
              {!isMinimized && messages.length > 0 && (
                <button
                  onClick={handleClearHistory}
                  title="Clear conversation"
                  className="p-1 rounded hover:bg-gov-800 hover:text-white transition"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              )}

              {/* Expand / Shrink */}
              {!isMinimized && (
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  title={isExpanded ? "Collapse view" : "Expand view"}
                  className="p-1 rounded hover:bg-gov-800 hover:text-white transition"
                >
                  {isExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
                </button>
              )}

              {/* Minimize to bar */}
              <button
                onClick={() => setIsMinimized(!isMinimized)}
                title={isMinimized ? "Restore" : "Minimize"}
                className="p-1 rounded hover:bg-gov-800 hover:text-white transition"
              >
                {isMinimized ? <Maximize2 className="w-3.5 h-3.5" /> : <Minimize2 className="w-3.5 h-3.5" />}
              </button>

              {/* Close Chat */}
              <button
                onClick={() => setIsOpen(false)}
                title="Close chat"
                className="p-1 rounded hover:bg-gov-800 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Body and Input (when not minimized) */}
          {!isMinimized && (
            <>
              <ChatHistory
                messages={messages}
                isLoading={isLoading}
                error={error}
                onSelectPrompt={handleSendMessage}
              />
              <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
            </>
          )}
        </div>
      )}
    </>
  );
};
