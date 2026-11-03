import React, { useState } from "react";
import {
  MessageSquare,
  X,
  Minimize2,
  Maximize2,
  RotateCcw,
  ShieldCheck,
  Bot,
  Sparkles,
} from "lucide-react";
import { ChatMessage } from "../../types/api";
import { ChatHistory } from "./ChatHistory";
import { ChatInput } from "./ChatInput";

interface FloatingChatbotProps {
  isOpen: boolean;
  onToggle: () => void;
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  onSendMessage: (message: string) => void;
  onClearHistory: () => void;
  selectedImportId: string;
  selectedImportName?: string;
}

export const FloatingChatbot: React.FC<FloatingChatbotProps> = ({
  isOpen,
  onToggle,
  messages,
  isLoading,
  error,
  onSendMessage,
  onClearHistory,
  selectedImportId,
  selectedImportName = "Latest Snapshot",
}) => {
  const [isMinimized, setIsMinimized] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <>
      {/* Floating Trigger Button (when closed) */}
      {!isOpen && (
        <button
          onClick={onToggle}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-3 bg-gov-900 hover:bg-gov-800 text-white rounded-full shadow-2xl border border-gov-700 hover:scale-105 transition duration-150 group"
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
          className={`fixed z-40 transition-all duration-200 shadow-2xl flex flex-col bg-slate-50 border border-slate-300 rounded-2xl overflow-hidden ${
            isMinimized
              ? "bottom-6 right-6 w-80 h-14"
              : isExpanded
              ? "bottom-6 right-6 w-[92vw] sm:w-[680px] h-[85vh] max-h-[850px]"
              : "bottom-6 right-6 w-[92vw] sm:w-[460px] h-[640px] max-h-[90vh]"
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
                <p className="text-[10px] text-gov-300 font-mono truncate max-w-[180px]">
                  Batch: {selectedImportName}
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-1 text-gov-300">
              {/* Clear conversation */}
              {!isMinimized && messages.length > 0 && (
                <button
                  onClick={onClearHistory}
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
                onClick={onToggle}
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
                onSelectPrompt={onSendMessage}
              />
              <ChatInput onSendMessage={onSendMessage} isLoading={isLoading} />
            </>
          )}
        </div>
      )}
    </>
  );
};

