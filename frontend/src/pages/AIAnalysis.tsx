import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { 
  Cpu, 
  ShieldAlert, 
  CheckCircle2, 
  AlertTriangle, 
  Play, 
  Sparkles, 
  Search, 
  FileDown, 
  X, 
  ArrowRight, 
  Eye, 
  ShieldCheck, 
  Activity, 
  Check, 
  Terminal, 
  Radio,
  MapPin,
  Clock,
  ChevronDown
} from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { mockInvestigations } from '../data/mockData';
import { Investigation } from '../types';

export const AIAnalysis: React.FC = () => {
  const [investigations, setInvestigations] = useState<Investigation[]>(mockInvestigations);
  const [isRunning, setIsRunning] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [isTerminalExpanded, setIsTerminalExpanded] = useState(false);
  
  // Navigation & Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState<'All' | 'High' | 'Medium' | 'Low'>('All');
  const [districtFilter, setDistrictFilter] = useState('All');
  const [selectedCase, setSelectedCase] = useState<Investigation | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const agentDefinitions = [
    {
      id: 1,
      name: 'Agent 1: Velocity Sentinel',
      role: 'Transaction Frequency & Velocity',
      desc: 'Monitors millisecond distribution intervals across FPS POS machines',
      status: 'Active Telemetry'
    },
    {
      id: 2,
      name: 'Agent 2: Spatial Graph Auditor',
      role: 'Geographic Radius Validation',
      desc: 'Cross-checks beneficiary location data against registered center bounds',
      status: 'Spatial Graph Sync'
    },
    {
      id: 3,
      name: 'Agent 3: Ledger Verifier',
      role: 'Zero-Knowledge Quota Integrity',
      desc: 'Reconciles grain dispatch balances with central FCI silo ledgers',
      status: 'Ledger Audit'
    },
    {
      id: 4,
      name: 'Agent 4: Risk Synthesizer',
      role: 'Bayesian Anomaly Scoring',
      desc: 'Aggregates multi-agent confidence metrics and triggers alert cascades',
      status: 'Model Scoring'
    }
  ];

  const startAnalysis = () => {
    setIsRunning(true);
    setActiveStep(1);
    setLogs([]);
    setIsTerminalExpanded(true);

    const agentSteps = [
      { step: 1, msg: '[Agent 1] Scanning active POS transaction streams for frequency spikes...' },
      { step: 1, msg: '[Agent 1] Detected 14 rapid back-to-back distributions (<45s) at FPS BENX1.' },
      { step: 2, msg: '[Agent 2] Cross-referencing GPS telemetry radius against East Delhi district boundary.' },
      { step: 2, msg: '[Agent 2] Spatial anomaly confirmed: 3 terminal requests generated beyond geographical margin.' },
      { step: 3, msg: '[Agent 3] Cryptographic ledger audit initiated against state buffer stock allocations...' },
      { step: 3, msg: '[Agent 3] Commodity discrepancy flagged: 500kg Wheat variance without ledger verification.' },
      { step: 4, msg: '[Agent 4] Bayesian fraud likelihood synthesized with 94.8% confidence rating.' },
      { step: 4, msg: '[Agent 4] Dispatched priority investigation dossier to State Food Inspectorate.' }
    ];

    agentSteps.forEach((item, idx) => {
      setTimeout(() => {
        setLogs(prev => [...prev, `${new Date().toLocaleTimeString()} - ${item.msg}`]);
        setActiveStep(item.step);
        if (idx === agentSteps.length - 1) {
          setTimeout(() => {
            setIsRunning(false);
            showToast('Multi-Agent Analysis run completed. 1 new anomaly identified and updated in registry.');
          }, 600);
        }
      }, (idx + 1) * 650);
    });
  };

  const handleResolveCase = (id: string, actionType: string) => {
    setInvestigations(prev => prev.map(inv => {
      if (inv.id === id) {
        return { ...inv, status: 'Resolved' };
      }
      return inv;
    }));
    setSelectedCase(null);
    showToast(`Action "${actionType}" executed successfully for case #${id}.`);
  };

  const handleExportAudit = () => {
    const headers = "Case ID,Title,FPS Center,District,Severity,Confidence,Reasoning,Recommended Action\n";
    const rows = filteredInvestigations.map(item => 
      `"${item.id}","${item.title}","${item.fps}","${item.district}","${item.severity}","${item.confidence}%","${item.reasoning.replace(/"/g, '""')}","${item.recommendedAction.replace(/"/g, '""')}"`
    ).join("\n");
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ai-audit-dossier-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    showToast("Neural audit report downloaded as CSV.");
  };

  // Filter calculations
  const filteredInvestigations = investigations.filter(item => {
    const matchesSearch = 
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.fps.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.district.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.reasoning.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesSeverity = severityFilter === 'All' || item.severity === severityFilter;
    const matchesDistrict = districtFilter === 'All' || item.district === districtFilter;

    return matchesSearch && matchesSeverity && matchesDistrict;
  });

  const uniqueDistricts = ['All', ...Array.from(new Set(investigations.map(i => i.district)))];

  const highSeverityCount = investigations.filter(i => i.severity === 'High' || i.severity === 'Critical').length;
  const mediumSeverityCount = investigations.filter(i => i.severity === 'Medium').length;
  const lowSeverityCount = investigations.filter(i => i.severity === 'Low').length;

  return (
    <div className="space-y-6 pb-12">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-[120] flex items-center gap-3 bg-[#0a3d2e] text-white px-5 py-3.5 rounded-2xl shadow-2xl border border-[#7fd8aa]/40 animate-in fade-in slide-in-from-bottom-5">
          <CheckCircle2 size={18} className="text-[#7fd8aa]" />
          <span className="text-xs md:text-sm font-semibold">{toastMessage}</span>
          <button onClick={() => setToastMessage(null)} className="ml-2 text-white/60 hover:text-white cursor-pointer">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl md:text-3xl font-extrabold text-[#10261c] tracking-tight font-display">
              AI Multi-Agent Neural Analysis
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase bg-[#2fa56f]/15 text-[#0d6840] border border-[#2fa56f]/30 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2fa56f] animate-pulse"></span>
              4 Agents Online
            </span>
          </div>
          <p className="text-xs md:text-sm text-[#5d7468] mt-1 font-medium">
            Continuous telemetry auditing, spatial anomaly detection, and automated fraud-risk scoring.
          </p>
        </div>

        {/* Action Header Buttons */}
        <div className="flex items-center gap-2.5 self-start sm:self-center">
          <button
            type="button"
            onClick={handleExportAudit}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full border border-slate-200/80 bg-white/80 hover:bg-white text-xs md:text-sm font-bold text-[#10261c] shadow-xs transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          >
            <FileDown size={15} className="text-[#5d7468]" />
            <span>Export Audit Log</span>
          </button>

          <button
            type="button"
            onClick={startAnalysis}
            disabled={isRunning}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full font-bold text-xs md:text-sm shadow-md transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-60 cursor-pointer !text-white text-white shrink-0"
            style={{
              background: 'linear-gradient(135deg, #14654a 0%, #1ea368 50%, #2fa56f 100%)',
              color: '#ffffff',
              boxShadow: '0 8px 20px -4px rgba(20, 101, 74, 0.4)'
            }}
          >
            {isRunning ? (
              <>
                <Radio size={16} className="text-white animate-spin" />
                <span className="font-bold text-white">Running Agents...</span>
              </>
            ) : (
              <>
                <Play size={16} className="text-white fill-white" />
                <span className="font-bold text-white">Trigger Detection Run</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* 4 Luxury Glass KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Total Detections */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Total Detections</span>
            <div className="w-8 h-8 rounded-full bg-cyan-500/12 flex items-center justify-center text-cyan-700">
              <Cpu size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">1,248</span>
            <span className="text-[11px] font-bold text-[#0d6840]">+14.2% vs last cycle</span>
          </div>
        </div>

        {/* KPI 2: High Risk Detections */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">High Risk Detections</span>
            <div className="w-8 h-8 rounded-full bg-[#ef5b4a]/15 flex items-center justify-center text-[#ef5b4a]">
              <ShieldAlert size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#ef5b4a] font-display">148</span>
            <span className="text-[11px] font-bold text-[#ef5b4a] bg-red-100/70 px-2 py-0.5 rounded-full">
              Action Required
            </span>
          </div>
        </div>

        {/* KPI 3: Detection Rate */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Detection Ratio</span>
            <div className="w-8 h-8 rounded-full bg-amber-500/15 flex items-center justify-center text-amber-700">
              <AlertTriangle size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">1.82%</span>
            <span className="text-[11px] font-bold text-amber-700">Threshold &lt; 2.5%</span>
          </div>
        </div>

        {/* KPI 4: Verification Rate */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Agent Precision</span>
            <div className="w-8 h-8 rounded-full bg-[#14654a]/12 flex items-center justify-center text-[#14654a]">
              <CheckCircle2 size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#14654a] font-display">98.4%</span>
            <span className="text-[11px] font-bold text-[#14654a] flex items-center gap-1">
              <ShieldCheck size={13} />
              Validated
            </span>
          </div>
        </div>
      </div>

      {/* Autonomous Multi-Agent Pipeline Control Stage */}
      <div className="bg-white/90 backdrop-blur-xl border border-white/90 rounded-[28px] p-6 shadow-sm space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-[#062d22] via-[#14654a] to-[#2fa56f] text-white flex items-center justify-center shadow-xs">
              <Activity size={20} />
            </div>
            <div>
              <h3 className="font-extrabold text-[#10261c] text-base md:text-lg font-display tracking-tight">
                Autonomous Multi-Agent Detection Pipeline
              </h3>
              <p className="text-xs text-[#5d7468] font-medium">
                Distributed neural consensus for zero-touch anomaly classification
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {logs.length > 0 && (
              <button
                type="button"
                onClick={() => setIsTerminalExpanded(!isTerminalExpanded)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                <Terminal size={14} className="text-[#14654a]" />
                <span>{isTerminalExpanded ? 'Hide Live Terminal' : 'View Live Terminal'}</span>
              </button>
            )}
            <button
              type="button"
              onClick={startAnalysis}
              disabled={isRunning}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold text-white shadow-sm transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer disabled:opacity-60"
              style={{
                background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)'
              }}
            >
              {isRunning ? <Radio size={14} className="animate-pulse" /> : <Play size={14} className="fill-white" />}
              <span>{isRunning ? 'Auditing Telemetry...' : 'Run Pipeline'}</span>
            </button>
          </div>
        </div>

        {/* 4 Agent Visual Pipeline Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {agentDefinitions.map((agent) => {
            const isCurrentActive = isRunning && activeStep === agent.id;
            const isCompleted = isRunning ? activeStep > agent.id : logs.length > 0;

            return (
              <div 
                key={agent.id}
                className={`p-4 rounded-2xl border transition-all relative overflow-hidden flex flex-col justify-between ${
                  isCurrentActive 
                    ? 'bg-emerald-50/80 border-[#14654a] shadow-md ring-2 ring-[#14654a]/20' 
                    : isCompleted
                    ? 'bg-white border-emerald-200/90 shadow-xs'
                    : 'bg-slate-50/70 border-slate-200/80'
                }`}
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#7a8b84]">
                      Stage 0{agent.id}
                    </span>
                    {isCurrentActive ? (
                      <span className="flex items-center gap-1 text-[10px] font-extrabold text-[#14654a] bg-emerald-100/90 px-2 py-0.5 rounded-full animate-pulse">
                        <Radio size={10} className="animate-spin" /> Processing
                      </span>
                    ) : isCompleted ? (
                      <span className="flex items-center gap-1 text-[10px] font-extrabold text-emerald-800 bg-emerald-100/70 px-2 py-0.5 rounded-full">
                        <Check size={10} strokeWidth={3} /> Verified
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold text-slate-400 bg-slate-200/60 px-2 py-0.5 rounded-full">
                        Standby
                      </span>
                    )}
                  </div>

                  <div>
                    <h4 className="font-extrabold text-[#10261c] text-xs font-display">
                      {agent.name}
                    </h4>
                    <p className="text-[11px] text-[#5d7468] mt-0.5 font-medium leading-relaxed">
                      {agent.desc}
                    </p>
                  </div>
                </div>

                <div className="pt-3 mt-3 border-t border-slate-200/50 flex items-center justify-between text-[10.5px]">
                  <span className="font-semibold text-slate-500">{agent.role}</span>
                  <span className="font-bold text-[#14654a]">{agent.status}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Real-time Streaming Terminal */}
        {logs.length > 0 && isTerminalExpanded && (
          <div className="rounded-2xl overflow-hidden border border-slate-800 shadow-xl animate-in fade-in duration-200">
            <div className="bg-slate-950 px-4 py-2.5 flex items-center justify-between border-b border-slate-800 text-xs font-mono text-slate-400">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500/80"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80"></span>
                <span className="text-slate-300 font-bold ml-1">neural-telemetry-engine.sh</span>
              </div>
              <span className="text-[11px] text-[#7fd8aa]">ACTIVE STREAM</span>
            </div>
            <div 
              ref={logContainerRef} 
              className="bg-slate-900 font-mono text-xs text-slate-300 p-4 space-y-1.5 max-h-48 overflow-y-auto"
            >
              {logs.map((log, i) => (
                <div key={i} className="flex items-start gap-2 leading-relaxed">
                  <span className="text-[#2fa56f] shrink-0 font-bold">&gt;</span>
                  <span className="text-slate-200">{log}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Interactive Navigation, Search & Severity Filters */}
      <div className="bg-white/90 backdrop-blur-xl border border-white/90 rounded-[28px] p-5 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3.5">
          {/* Severity Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
            <button
              onClick={() => setSeverityFilter('All')}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer ${
                severityFilter === 'All'
                  ? 'bg-[#14654a] text-white shadow-xs'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
              }`}
            >
              All Anomalies ({investigations.length})
            </button>

            <button
              onClick={() => setSeverityFilter('High')}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                severityFilter === 'High'
                  ? 'bg-red-600 text-white shadow-xs'
                  : 'bg-red-50 hover:bg-red-100 text-red-700'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span>
              High Risk ({highSeverityCount})
            </button>

            <button
              onClick={() => setSeverityFilter('Medium')}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                severityFilter === 'Medium'
                  ? 'bg-amber-600 text-white shadow-xs'
                  : 'bg-amber-50 hover:bg-amber-100 text-amber-700'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
              Medium ({mediumSeverityCount})
            </button>

            <button
              onClick={() => setSeverityFilter('Low')}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                severityFilter === 'Low'
                  ? 'bg-cyan-700 text-white shadow-xs'
                  : 'bg-cyan-50 hover:bg-cyan-100 text-cyan-800'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-500"></span>
              Low ({lowSeverityCount})
            </button>
          </div>

          {/* Search & District Selector */}
          <div className="flex items-center gap-2.5">
            {/* District Dropdown */}
            <div className="relative">
              <select
                value={districtFilter}
                onChange={(e) => setDistrictFilter(e.target.value)}
                className="pl-3 pr-8 py-2 rounded-full border border-slate-200/90 bg-slate-50/80 hover:bg-white text-xs font-bold text-[#10261c] focus:outline-none focus:border-[#14654a] appearance-none cursor-pointer"
              >
                {uniqueDistricts.map(dist => (
                  <option key={dist} value={dist}>
                    {dist === 'All' ? 'All Districts' : dist}
                  </option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>

            {/* Search Input */}
            <div className="relative min-w-[220px]">
              <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search FPS, center, pattern..."
                className="w-full pl-9 pr-3.5 py-2 rounded-full border border-slate-200/90 bg-slate-50/80 hover:bg-white focus:bg-white text-xs text-[#10261c] placeholder-slate-400 focus:outline-none focus:border-[#14654a] transition-all font-medium"
              />
              {searchQuery && (
                <button 
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* AI Detection Feed Cards */}
        <div className="space-y-3 pt-2">
          {filteredInvestigations.length === 0 ? (
            <div className="text-center py-12 bg-slate-50/50 rounded-2xl border border-dashed border-slate-200">
              <Sparkles size={24} className="mx-auto text-slate-400 mb-2" />
              <p className="text-sm font-bold text-[#10261c]">No anomalies matched your filter</p>
              <p className="text-xs text-[#7a8b84] mt-0.5">Try resetting search keywords or selecting All Anomalies.</p>
              <button
                type="button"
                onClick={() => { setSearchQuery(''); setSeverityFilter('All'); setDistrictFilter('All'); }}
                className="mt-3 px-4 py-1.5 rounded-full text-xs font-bold text-[#14654a] bg-[#14654a]/10 hover:bg-[#14654a]/15 cursor-pointer transition-colors"
              >
                Clear all filters
              </button>
            </div>
          ) : (
            filteredInvestigations.map((item) => (
              <div 
                key={item.id}
                className="bg-white border border-slate-100 hover:border-emerald-300/80 rounded-2xl p-5 shadow-xs hover:shadow-md transition-all duration-200 space-y-3.5"
              >
                {/* Card Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span className="font-mono font-extrabold text-xs text-[#10261c] bg-slate-100/90 px-2.5 py-1 rounded-lg border border-slate-200/70">
                      FPS: {item.fps}
                    </span>
                    <span className="text-xs font-semibold text-slate-500 flex items-center gap-1">
                      <MapPin size={12} className="text-[#14654a]" />
                      {item.district}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-xs text-slate-400 flex items-center gap-1">
                      <Clock size={12} />
                      {item.updatedAt}
                    </span>
                    {item.status === 'Resolved' && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800">
                        Resolved
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <StatusBadge type={item.severity} text={item.severity} />
                    <span className="text-[11px] font-extrabold text-[#14654a] bg-[#14654a]/8 px-2.5 py-0.5 rounded-full border border-[#14654a]/20">
                      {item.confidence}% Confidence
                    </span>
                  </div>
                </div>

                {/* Case Title */}
                <div>
                  <h4 className="font-extrabold text-[#10261c] text-sm md:text-base font-display">
                    {item.title}
                  </h4>
                </div>

                {/* AI Neural Reasoning Callout */}
                <div className="flex items-start gap-3 bg-[#f2f8f5]/90 border border-[#d3ebd9] p-3.5 rounded-2xl">
                  <div className="w-6 h-6 rounded-lg bg-[#14654a]/15 text-[#14654a] flex items-center justify-center shrink-0 mt-0.5">
                    <Sparkles size={13} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[#14654a] block">
                      Autonomous Neural Reasoning
                    </span>
                    <p className="text-xs text-slate-700 leading-relaxed font-medium mt-0.5">
                      {item.reasoning}
                    </p>
                  </div>
                </div>

                {/* Card Actions & Footer */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1 border-t border-slate-100/80">
                  <div className="text-xs text-[#5d7468]">
                    <span className="font-bold text-[#10261c]">Recommended Protocol: </span>
                    <span className="truncate">{item.recommendedAction}</span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => setSelectedCase(item)}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold text-[#14654a] bg-[#14654a]/10 hover:bg-[#14654a]/20 transition-colors cursor-pointer"
                    >
                      <Eye size={13} />
                      <span>Inspect Dossier</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleResolveCase(item.id, 'Dispatched Field Inspector')}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold text-white shadow-xs transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
                      style={{
                        background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)'
                      }}
                    >
                      <span>Take Action</span>
                      <ArrowRight size={12} />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* =====================================================================
          DETAILED AI INVESTIGATION DOSSIER MODAL
          ===================================================================== */}
      {selectedCase && createPortal(
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setSelectedCase(null)}
        >
          <div 
            className="w-full max-w-[580px] rounded-[32px] overflow-hidden flex flex-col bg-white border border-slate-100 shadow-[0_24px_70px_-12px_rgba(16,38,28,0.3)] animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-7 py-5 border-b border-slate-100 bg-gradient-to-b from-[#f2f8f5]/90 to-white">
              <div className="flex items-center gap-3.5 flex-1 min-w-0 pr-3">
                <div 
                  className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 shadow-md shadow-[#14654a]/20"
                  style={{
                    background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
                    color: '#ffffff'
                  }}
                >
                  <ShieldAlert size={22} className="text-white" strokeWidth={2.2} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-extrabold text-[#10261c] text-lg font-display tracking-tight truncate">
                      Investigation Dossier #{selectedCase.id}
                    </h3>
                    <StatusBadge type={selectedCase.severity} text={selectedCase.severity} />
                  </div>
                  <p className="text-xs text-[#5d7468] mt-0.5 font-medium">
                    Telemetry Analysis & Anomaly Evidence Record
                  </p>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => setSelectedCase(null)} 
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-800 bg-slate-100/80 hover:bg-slate-200/80 transition-all shrink-0 cursor-pointer hover:rotate-90 duration-200"
                aria-label="Close dialog"
              >
                <X size={16} strokeWidth={2.2} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-7 space-y-4.5 text-xs md:text-sm">
              {/* Center & Confidence Stats Card */}
              <div className="grid grid-cols-2 gap-3 p-4 rounded-2xl bg-slate-50/80 border border-slate-200/80">
                <div>
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wider block">Target Center</span>
                  <span className="font-mono font-bold text-sm text-[#10261c]">{selectedCase.fps}</span>
                  <span className="text-[11px] text-slate-500 block">{selectedCase.district} District</span>
                </div>
                <div>
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wider block">Neural Confidence</span>
                  <span className="font-extrabold text-sm text-[#14654a]">{selectedCase.confidence}% Certainty</span>
                  <span className="text-[11px] text-emerald-700 block">Verified by 3 Agents</span>
                </div>
              </div>

              {/* Anomaly Synopsis */}
              <div className="space-y-1">
                <span className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                  Anomaly Synopsis
                </span>
                <p className="text-xs font-semibold text-[#10261c] bg-slate-50 p-3 rounded-xl border border-slate-100">
                  {selectedCase.title}
                </p>
              </div>

              {/* Agent Reasoning */}
              <div className="space-y-1">
                <span className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                  Telemetry Evidence & Reasoning
                </span>
                <div className="p-3.5 rounded-2xl bg-[#f2f8f5]/90 border border-[#d3ebd9] text-xs text-slate-700 leading-relaxed font-medium">
                  {selectedCase.reasoning}
                </div>
              </div>

              {/* Recommended Action Protocol */}
              <div className="space-y-1">
                <span className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                  Prescribed Administrative Protocol
                </span>
                <p className="text-xs text-slate-600 bg-amber-50/80 border border-amber-200/70 p-3 rounded-xl font-medium leading-relaxed">
                  {selectedCase.recommendedAction}
                </p>
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => handleResolveCase(selectedCase.id, 'Dismissed False Positive')}
                  className="px-4 py-2.5 rounded-full text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Dismiss Anomaly
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleResolveCase(selectedCase.id, 'Frozen Grain Quota')}
                    className="px-4 py-2.5 rounded-full text-xs font-bold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200/70 transition-colors cursor-pointer"
                  >
                    Freeze Quota
                  </button>
                  <button
                    type="button"
                    onClick={() => handleResolveCase(selectedCase.id, 'Field Inspector Dispatched')}
                    className="px-5 py-2.5 rounded-full text-xs font-bold text-white shadow-md transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
                    style={{
                      background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
                      boxShadow: '0 8px 18px -4px rgba(20, 101, 74, 0.45)'
                    }}
                  >
                    Deploy Field Inspector
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};
