import React, { useState, useEffect, useRef } from 'react';
import { Cpu, ShieldAlert, CheckCircle2, AlertTriangle, Play, Sparkles } from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { mockInvestigations } from '../data/mockData';

export const AIAnalysis: React.FC = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const startAnalysis = () => {
    setIsRunning(true);
    setLogs([]);
    const messages = [
      'Initializing Agent 1: Transaction Analyst...',
      'Agent 1: Scanning database for suspicious transaction frequencies...',
      'Agent 1: Identified 14 potential timing patterns at BENX1.',
      'Initializing Agent 2: Anomaly Investigator...',
      'Agent 2: Loading deterministic ledger verification tools...',
      'Agent 2: Verified time delta anomalies on 3 transactions.',
      'Initializing Agent 3: Evidence Case Builder...',
      'Agent 3: Compiling case statistics and spatial metrics...',
      'Agent 3: Confidence score generated: 94%.',
      'Initializing Agent 4: Alert Generator...',
      'Agent 4: Formatting dashboard-ready JSON payload...',
      'Alert Center payload updated successfully.'
    ];

    messages.forEach((msg, idx) => {
      setTimeout(() => {
        setLogs(prev => [...prev, msg]);
        if (idx === messages.length - 1) setIsRunning(false);
      }, (idx + 1) * 400);
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">AI Analysis</h1>
        <p className="text-xs md:text-sm text-slate-500 mt-1">
          Select parameters and execute the multi-agent detection pipeline.
        </p>
      </div>

      {/* Control Panel */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-slate-800 text-sm md:text-base">Trigger Multi-Agent Detection Run</h3>
          <button
            onClick={startAnalysis}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-4 py-2 bg-[#0284C7] hover:bg-[#0369A1] disabled:opacity-50 text-white text-xs font-bold rounded shadow-xs transition-colors"
          >
            <Play size={14} />
            <span>{isRunning ? 'Running agents...' : 'Start Run'}</span>
          </button>
        </div>

        {/* Live log panel */}
        {logs.length > 0 && (
          <div ref={logContainerRef} className="bg-slate-900 font-mono text-[10px] md:text-xs text-slate-300 p-4 rounded-lg space-y-1 max-h-48 overflow-y-auto border border-slate-800">
            {logs.map((log, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-[#0284C7]">&gt;</span>
                <span>{log}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded bg-blue-50 text-[#0284C7] flex items-center justify-center shrink-0">
            <Cpu size={20} />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Total Detections</span>
            <span className="text-lg font-bold text-slate-800">1,248</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded bg-red-50 text-red-600 flex items-center justify-center shrink-0">
            <ShieldAlert size={20} />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">High Risk Detections</span>
            <span className="text-lg font-bold text-slate-800">148</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded bg-yellow-50 text-yellow-600 flex items-center justify-center shrink-0">
            <AlertTriangle size={20} />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Detection Rate</span>
            <span className="text-lg font-bold text-slate-800">1.82%</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded bg-green-50 text-green-600 flex items-center justify-center shrink-0">
            <CheckCircle2 size={20} />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Verification Rate</span>
            <span className="text-lg font-bold text-slate-800">92.4%</span>
          </div>
        </div>
      </div>

      {/* AI Feed list */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
        <h3 className="font-bold text-slate-800 text-sm md:text-base">AI Agent Detection Feed</h3>
        <div className="divide-y divide-slate-100">
          {mockInvestigations.map((item) => (
            <div key={item.id} className="py-4 first:pt-0 last:pb-0 flex flex-col gap-2.5 text-xs md:text-sm">
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold text-slate-800">{item.title}</span>
                  <span className="text-slate-300">|</span>
                  <span className="text-xs font-semibold text-slate-500">FPS: {item.fps}</span>
                  <span className="text-slate-300">•</span>
                  <span className="text-xs text-slate-400">{item.updatedAt}</span>
                </div>
                <StatusBadge type={item.severity} text={item.severity} />
              </div>
              <div className="flex items-start gap-2 bg-sky-50/20 border border-sky-100/50 p-3 rounded">
                <Sparkles size={14} className="text-sky-500 shrink-0 mt-0.5" />
                <p className="text-slate-600 text-xs leading-relaxed">{item.reasoning}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
