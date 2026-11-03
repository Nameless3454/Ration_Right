import React, { useState } from "react";
import {
  ShieldAlert,
  Database,
  BookOpen,
  Info,
  ChevronDown,
  ChevronUp,
  User,
  Bot,
  CheckCircle2,
} from "lucide-react";
import { ChatMessage } from "../../types/api";

interface ChatMessageItemProps {
  message: ChatMessage;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({ message }) => {
  const [showEvidence, setShowEvidence] = useState(false);
  const isAssistant = message.sender === "assistant";
  const meta = message.responseMeta;

  // Format assistant markdown response for clean UI display
  const renderFormattedText = (rawText: string) => {
    const lines = rawText.split("\n");
    const elements: React.ReactNode[] = [];
    let inAlert = false;
    let alertType = "";
    let alertLines: string[] = [];

    let inTable = false;
    let tableLines: string[] = [];

    const flushAlert = (key: number) => {
      if (alertLines.length > 0) {
        const alertContent = alertLines.join(" ");
        let alertStyles = "bg-blue-50 border-blue-300 text-blue-900";
        let icon = <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />;

        if (alertType.includes("IMPORTANT") || alertType.includes("WARNING")) {
          alertStyles = "bg-amber-50 border-amber-300 text-amber-950";
          icon = <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />;
        }

        elements.push(
          <div key={`alert-${key}`} className={`my-2.5 p-3 border-l-4 rounded-r-lg text-xs flex gap-2 ${alertStyles}`}>
            {icon}
            <div className="space-y-1">{alertContent}</div>
          </div>
        );
        alertLines = [];
        inAlert = false;
        alertType = "";
      }
    };

    const flushTable = (key: number) => {
      if (tableLines.length >= 2) {
        const headers = tableLines[0]
          .split("|")
          .slice(1, -1)
          .map((c) => c.trim());
        const bodyRows = tableLines.slice(2).map((l) =>
          l
            .split("|")
            .slice(1, -1)
            .map((c) => c.trim())
        );

        elements.push(
          <div key={`table-${key}`} className="my-3 overflow-x-auto rounded-lg border border-slate-200 shadow-xs">
            <table className="w-full text-[11px] text-left border-collapse">
              <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                <tr>
                  {headers.map((h, i) => (
                    <th key={i} className="px-2.5 py-1.5 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {bodyRows.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-slate-50/80 transition">
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="px-2.5 py-1.5 text-slate-800 whitespace-nowrap">
                        {renderInlineMarkdown(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      tableLines = [];
      inTable = false;
    };

    lines.forEach((line, idx) => {
      // Table handling
      if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
        if (!inTable) {
          flushAlert(idx);
          inTable = true;
        }
        tableLines.push(line.trim());
        return;
      } else if (inTable) {
        flushTable(idx);
      }

      // GitHub style alerts detection
      if (line.startsWith("> [!")) {
        flushAlert(idx);
        inAlert = true;
        alertType = line;
        return;
      }
      if (inAlert) {
        if (line.startsWith(">")) {
          alertLines.push(line.replace(/^>\s?/, ""));
          return;
        } else {
          flushAlert(idx);
        }
      }

      // Source footnote detection: *Source: ...*
      if (line.trim().startsWith("*Source:") && line.trim().endsWith("*")) {
        flushAlert(idx);
        const sourceText = line.trim().replace(/^\*|\*$/g, "");
        elements.push(
          <div key={`source-${idx}`} className="mt-3 pt-2 border-t border-slate-100 flex items-center gap-1.5 text-[10px] text-slate-500">
            <Database className="w-3.5 h-3.5 text-gov-600 shrink-0" />
            <span>{renderInlineMarkdown(sourceText)}</span>
          </div>
        );
        return;
      }

      // Headers
      if (line.startsWith("### ")) {
        elements.push(
          <h4 key={idx} className="font-bold text-slate-900 text-sm mt-3 mb-1">
            {line.replace("### ", "")}
          </h4>
        );
        return;
      }
      if (line.startsWith("#### ")) {
        elements.push(
          <h5 key={idx} className="font-semibold text-slate-800 text-xs mt-2 mb-1">
            {line.replace("#### ", "")}
          </h5>
        );
        return;
      }

      // Bullet items
      if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
        const itemText = line.trim().replace(/^[-*]\s+/, "");
        elements.push(
          <li key={idx} className="ml-4 list-disc text-xs text-slate-800 my-0.5 leading-relaxed">
            {renderInlineMarkdown(itemText)}
          </li>
        );
        return;
      }

      // Numbered items
      if (/^\d+\.\s+/.test(line.trim())) {
        elements.push(
          <div key={idx} className="text-xs text-slate-800 my-1 font-medium">
            {renderInlineMarkdown(line.trim())}
          </div>
        );
        return;
      }

      // Standard paragraphs
      if (line.trim().length > 0) {
        elements.push(
          <p key={idx} className="text-xs text-slate-800 my-1.5 leading-relaxed">
            {renderInlineMarkdown(line)}
          </p>
        );
      }
    });

    if (inTable) flushTable(lines.length);
    flushAlert(lines.length);
    return elements;
  };

  // Inline formatting for **bold**, `code`, and *italics*
  const renderInlineMarkdown = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*|\`.*?\`|\*.*?\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i} className="font-bold text-slate-950">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={i} className="px-1 py-0.5 rounded bg-slate-100 text-gov-800 font-mono text-[11px] border border-slate-200">
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={i} className="italic text-slate-600">{part.slice(1, -1)}</em>;
      }
      return part;
    });
  };

  return (
    <div className={`flex gap-2.5 my-3 ${isAssistant ? "items-start" : "items-start flex-row-reverse"}`}>
      {/* Avatar */}
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs shadow-sm ${
          isAssistant
            ? "bg-gov-800 text-india-saffron border border-gov-700"
            : "bg-slate-700 text-white"
        }`}
      >
        {isAssistant ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
      </div>

      {/* Message Bubble Container */}
      <div
        className={`max-w-[88%] rounded-2xl px-4 py-3 shadow-sm ${
          isAssistant
            ? "bg-white border border-slate-200 text-slate-900 rounded-tl-sm"
            : "bg-gov-700 text-white rounded-tr-sm"
        }`}
      >
        {/* Assistant Header with Clean Official Context */}
        {isAssistant && (
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 text-[11px]">
            <div className="flex items-center gap-1.5 font-semibold text-gov-800">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>RationRight Assistant</span>
            </div>
            <div className="flex items-center gap-1.5">
              {meta?.dataset_name_cited && (
                <span className="text-[10px] text-slate-600 font-medium bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200 font-sans">
                  {meta.dataset_name_cited}
                </span>
              )}
              {meta?.route_type && (
                <span
                  className={`text-[9px] px-1.5 py-0.5 rounded font-semibold uppercase tracking-wider ${
                    meta.route_type === "STRUCTURED"
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : meta.route_type === "RAG_DEFINITION"
                      ? "bg-purple-50 text-purple-700 border border-purple-200"
                      : meta.route_type === "HYBRID"
                      ? "bg-blue-50 text-blue-700 border border-blue-200"
                      : "bg-amber-50 text-amber-700 border border-amber-200"
                  }`}
                >
                  {meta.route_type === "STRUCTURED"
                    ? "Verified Record"
                    : meta.route_type === "RAG_DEFINITION"
                    ? "Policy Doc"
                    : meta.route_type === "HYBRID"
                    ? "Hybrid Brief"
                    : "Refusal"}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Message Body */}
        <div className="text-xs">
          {isAssistant ? (
            renderFormattedText(message.text)
          ) : (
            <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
          )}
        </div>

        {/* Collapsible Verified Evidence Accordion */}
        {isAssistant && meta?.evidence && (meta.evidence.sql_data || meta.evidence.rag_context) && (
          <div className="mt-3 pt-2 border-t border-slate-100">
            <button
              onClick={() => setShowEvidence(!showEvidence)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-gov-700 hover:text-gov-900 transition"
            >
              {showEvidence ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              <span>{showEvidence ? "Hide Verified Evidence" : "View Verified Evidence (SQL / RAG)"}</span>
            </button>

            {showEvidence && (
              <div className="mt-2 p-2.5 rounded-lg bg-slate-50 border border-slate-200 space-y-2 text-[11px] font-mono">
                {meta.evidence.sql_data && (
                  <div>
                    <span className="font-bold text-slate-700 block mb-1">SQL Query Evidence:</span>
                    <pre className="p-2 bg-slate-900 text-emerald-400 rounded text-[10px] overflow-x-auto max-h-48">
                      {JSON.stringify(meta.evidence.sql_data, null, 2)}
                    </pre>
                  </div>
                )}
                {meta.evidence.rag_context && meta.evidence.rag_context.length > 0 && (
                  <div>
                    <span className="font-bold text-slate-700 block mb-1">ChromaDB Documentation Sources:</span>
                    <div className="space-y-1.5">
                      {meta.evidence.rag_context.map((doc, docIdx) => (
                        <div key={docIdx} className="p-2 bg-white rounded border border-slate-200">
                          <p className="font-bold text-slate-800 text-[11px]">{doc.title}</p>
                          <p className="text-[10px] text-slate-500 mb-1">Category: {doc.category}</p>
                          <p className="text-[10px] text-slate-600 font-sans">{doc.content}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <div className="mt-1 text-[10px] text-right opacity-60">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </div>
  );
};
