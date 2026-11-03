import React from "react";
import { Database, ShieldCheck, UploadCloud, MessageSquare, Activity } from "lucide-react";
import { ImportBatchSummary } from "../types/api";

interface HeaderProps {
  imports: ImportBatchSummary[];
  selectedImportId: string;
  onSelectImport: (id: string) => void;
  onOpenUpload: () => void;
  onToggleChat: () => void;
  isChatOpen: boolean;
  systemStatus: "healthy" | "loading" | "error";
}

export const Header: React.FC<HeaderProps> = ({
  imports,
  selectedImportId,
  onSelectImport,
  onOpenUpload,
  onToggleChat,
  isChatOpen,
  systemStatus,
}) => {
  const currentImport = imports.find((i) => i.import_id === selectedImportId) || imports[0];

  return (
    <header className="bg-gov-900 border-b border-gov-800 text-white shadow-md sticky top-0 z-30">
      {/* Top tricolor subtle accent */}
      <div className="h-1 bg-gradient-to-r from-india-saffron via-white to-india-green" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        {/* Portal Title & Branding */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gov-800 border border-gov-700 flex items-center justify-center shadow-inner">
            <ShieldCheck className="w-6 h-6 text-india-saffron" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold tracking-wider text-india-saffron uppercase">
                National Food Security Portal
              </span>
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-gov-800/80 text-slate-300 border border-gov-700">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    systemStatus === "healthy"
                      ? "bg-emerald-400"
                      : systemStatus === "loading"
                      ? "bg-amber-400 animate-pulse"
                      : "bg-red-400"
                  }`}
                />
                {systemStatus === "healthy" ? "API Online" : systemStatus === "loading" ? "Connecting..." : "API Offline"}
              </span>
            </div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              RationRight <span className="text-gov-300 font-normal text-sm">AI Operations Assistant</span>
            </h1>
          </div>
        </div>

        {/* Action Controls & Snapshot Selector */}
        <div className="flex items-center flex-wrap gap-2.5">
          {/* Active Snapshot Picker */}
          <div className="flex items-center gap-2 bg-gov-800/90 border border-gov-700 rounded-lg px-3 py-1.5 shadow-sm">
            <Database className="w-4 h-4 text-gov-300" />
            <div className="flex flex-col text-left">
              <span className="text-[10px] text-gov-300 font-medium uppercase tracking-wider">
                Active Weekly Dataset
              </span>
              <select
                className="bg-transparent text-xs font-semibold text-white focus:outline-none cursor-pointer pr-4"
                value={selectedImportId}
                onChange={(e) => onSelectImport(e.target.value)}
              >
                <option value="latest" className="bg-gov-900 text-white">
                  Latest Snapshot {imports.length > 0 ? `(${imports[0]?.dataset_name})` : ""}
                </option>
                {imports.map((imp) => (
                  <option key={imp.import_id} value={imp.import_id} className="bg-gov-900 text-white">
                    {imp.dataset_name} ({imp.import_id.slice(-8)})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Upload Dataset Button */}
          <button
            onClick={onOpenUpload}
            className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg bg-gov-700 hover:bg-gov-600 text-white border border-gov-600 transition shadow-sm"
          >
            <UploadCloud className="w-4 h-4 text-gov-200" />
            <span>Upload Batch</span>
          </button>

          {/* Chat Open/Close Button */}
          <button
            onClick={onToggleChat}
            className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-lg transition shadow-sm ${
              isChatOpen
                ? "bg-india-saffron text-slate-950 hover:bg-amber-400"
                : "bg-gov-600 hover:bg-gov-500 text-white border border-gov-500"
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            <span>{isChatOpen ? "Close Assistant" : "Ask Assistant"}</span>
          </button>
        </div>
      </div>
    </header>
  );
};

