import React, { useRef, useEffect } from "react";
import { MessageSquare, ShieldCheck, Loader2, AlertCircle } from "lucide-react";
import { ChatMessage } from "../../types/api";
import { ChatMessageItem } from "./ChatMessageItem";

interface ChatHistoryProps {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  onSelectPrompt: (prompt: string) => void;
}

export const ChatHistory: React.FC<ChatHistoryProps> = ({
  messages,
  isLoading,
  error,
  onSelectPrompt,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const samplePrompts = [
    {
      title: "Beneficiary Queries",
      prompt: "How many beneficiaries are registered in the latest import?",
    },
    {
      title: "Duplicate Review Flags",
      prompt: "Which records have duplicate flags and what are their reasons?",
    },
    {
      title: "Inventory Stock Status",
      prompt: "What is the current stock of rice and wheat and are there any shortages?",
    },
    {
      title: "FPS Compliance & Audits",
      prompt: "Which shops have the highest citizen complaints and failed inspections?",
    },
    {
      title: "Welfare Policy Rules",
      prompt: "What does statutory quota mean and how is AAY entitlement determined?",
    },
    {
      title: "Historical Comparison",
      prompt: "Compare this week's inventory with the previous week snapshot.",
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      {messages.length === 0 ? (
        <div className="h-full flex flex-col justify-center items-center text-center p-4 max-w-md mx-auto my-auto space-y-4">
          <div className="w-12 h-12 rounded-xl bg-gov-100 flex items-center justify-center text-gov-700 shadow-sm">
            <ShieldCheck className="w-7 h-7 text-india-saffron" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-800">RationRight AI Operations Assistant</h3>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              Inquire about weekly beneficiary registrations, commodity ledgers, physical audit variances, and system flag definitions.
            </p>
          </div>

          <div className="w-full text-left space-y-1.5 pt-2">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Suggested Operational Inquiries:
            </p>
            <div className="grid grid-cols-1 gap-1.5">
              {samplePrompts.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectPrompt(p.prompt)}
                  className="p-2 text-left rounded-lg border border-slate-200 bg-white hover:bg-gov-50/70 hover:border-gov-300 transition text-xs group"
                >
                  <span className="font-semibold text-slate-800 block text-[11px] group-hover:text-gov-800">
                    {p.title}
                  </span>
                  <span className="text-slate-500 text-[11px] line-clamp-1">
                    {p.prompt}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <>
          {messages.map((msg) => (
            <ChatMessageItem key={msg.id} message={msg} />
          ))}

          {/* Loading Indicator */}
          {isLoading && (
            <div className="flex items-center gap-2 p-3 bg-white border border-slate-200 rounded-2xl w-fit shadow-sm text-xs text-slate-600">
              <Loader2 className="w-4 h-4 animate-spin text-gov-600" />
              <span>Querying verified SQLite evidence and policy docs...</span>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">
              <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div ref={bottomRef} />
        </>
      )}
    </div>
  );
};

