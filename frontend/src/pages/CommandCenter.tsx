import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { 
  Activity, 
  Radio, 
  ShieldAlert, 
  ShieldCheck, 
  Cpu, 
  Truck, 
  Warehouse, 
  Store, 
  Users, 
  BarChart3, 
  FileText, 
  AlertTriangle, 
  CheckCircle2, 
  RefreshCw, 
  ArrowUpRight, 
  ArrowRight, 
  Play, 
  Pause, 
  Lock, 
  Bell, 
  Boxes,
  X
} from 'lucide-react';

interface CommandCenterProps {
  onNavigate: (route: string) => void;
}

interface NetworkNode {
  id: string;
  name: string;
  type: 'central' | 'hub' | 'terminal';
  status: 'nominal' | 'warning' | 'synced';
  location: string;
  stock: string;
  capacity: string;
  throughput: string;
  activeTrucks: number;
  x: number;
  y: number;
}

interface StreamEvent {
  id: string;
  type: 'dispatch' | 'security' | 'inventory';
  title: string;
  subtitle: string;
  timestamp: string;
  badge: string;
  badgeColor: string;
  details: string;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({ onNavigate }) => {
  const [currentTime, setCurrentTime] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string>('central-fci');
  const [streamFilter, setStreamFilter] = useState<'all' | 'dispatch' | 'security' | 'inventory'>('all');
  const [emergencyModalOpen, setEmergencyModalOpen] = useState<boolean>(false);
  const [toast, setToast] = useState<string | null>(null);

  // Live real-time clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString('en-IN', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
      }) + ' IST');
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  const triggerToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3200);
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
      triggerToast('Telemetry grid re-synchronized with 414 FPS nodes.');
    }, 900);
  };

  // Supply Grid Network Nodes
  const networkNodes: NetworkNode[] = [
    {
      id: 'central-fci',
      name: 'FCI Godown #12 (Apex Reserve)',
      type: 'central',
      status: 'nominal',
      location: 'Central Grain Reserve, New Delhi',
      stock: '79,61,167 kg',
      capacity: '1,00,00,000 kg',
      throughput: '1,850 kg/min',
      activeTrucks: 24,
      x: 50,
      y: 20
    },
    {
      id: 'hub-north',
      name: 'North Silo Corridor (Delhi NCR)',
      type: 'hub',
      status: 'nominal',
      location: 'Okhla Industrial Buffer, Delhi',
      stock: '18,40,000 kg',
      capacity: '25,00,000 kg',
      throughput: '420 kg/min',
      activeTrucks: 8,
      x: 20,
      y: 55
    },
    {
      id: 'hub-central',
      name: 'Central Silo Corridor (Bhopal)',
      type: 'hub',
      status: 'nominal',
      location: 'Mandideep Logistics Center, MP',
      stock: '22,10,000 kg',
      capacity: '30,00,000 kg',
      throughput: '510 kg/min',
      activeTrucks: 7,
      x: 40,
      y: 60
    },
    {
      id: 'hub-east',
      name: 'East Silo Corridor (Lucknow)',
      type: 'hub',
      status: 'warning',
      location: 'Amausi Buffer Complex, UP',
      stock: '14,90,000 kg',
      capacity: '25,00,000 kg',
      throughput: '380 kg/min',
      activeTrucks: 5,
      x: 65,
      y: 55
    },
    {
      id: 'hub-west',
      name: 'West Silo Corridor (Pune)',
      type: 'hub',
      status: 'nominal',
      location: 'Chakan Strategic Godown, MH',
      stock: '24,21,167 kg',
      capacity: '30,00,000 kg',
      throughput: '540 kg/min',
      activeTrucks: 9,
      x: 82,
      y: 65
    },
    {
      id: 'terminals-grid',
      name: 'Statewide FPS Terminal Array',
      type: 'terminal',
      status: 'synced',
      location: '414 Licensed Fair Price Outlets',
      stock: '43,450.5 kg (Today Outflow)',
      capacity: '402 Online / 12 Standby',
      throughput: '4,100 tx/hr',
      activeTrucks: 42,
      x: 50,
      y: 90
    }
  ];

  const selectedNode = networkNodes.find(n => n.id === selectedNodeId) || networkNodes[0];

  // Streaming Telemetry Feed
  const streamEvents: StreamEvent[] = [
    {
      id: 'ev-1',
      type: 'dispatch',
      title: 'Biometric Quota Cleared: 35.0 kg Rice & Wheat',
      subtitle: 'FPS-DL-0012 (Okhla Center) • Beneficiary #BEN-89214',
      timestamp: '10s ago',
      badge: 'VERIFIED',
      badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      details: 'Aadhaar iris scan matched with zero margin discrepancy.'
    },
    {
      id: 'ev-2',
      type: 'security',
      title: 'AI Sentinel: Ghost Card Transaction Blocked',
      subtitle: 'FPS-DL-0044 • Cardholder BEN-90234 concurrent attempt',
      timestamp: '42s ago',
      badge: 'BLOCKED',
      badgeColor: 'bg-rose-50 text-rose-700 border-rose-200',
      details: 'Secondary terminal attempt detected across 24km distance in under 3 minutes.'
    },
    {
      id: 'ev-3',
      type: 'inventory',
      title: 'Buffer Consignment Inflow: +50,000 kg Rice Refill',
      subtitle: 'FCI Godown #12 -> East Delhi Silo • Challan FCI-CH-3676',
      timestamp: '2m ago',
      badge: 'IN TRANSIT',
      badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
      details: 'Logistics controller P.K. Verma authorized convoy dispatch.'
    },
    {
      id: 'ev-4',
      type: 'dispatch',
      title: 'FPS Sub-Store Stock Replenished: 8,500 kg Wheat',
      subtitle: 'FPS-LU-0098 (Lucknow Sector 4) • Local distributor delivery',
      timestamp: '4m ago',
      badge: 'DELIVERED',
      badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      details: 'Automatic balance reconciliation performed with zero variance.'
    },
    {
      id: 'ev-5',
      type: 'security',
      title: 'Volumetric Discrepancy Flagged: -420 kg Off-Cycle',
      subtitle: 'FPS Center BENX1 • Dealer audit requested',
      timestamp: '8m ago',
      badge: 'AUDIT REQ',
      badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
      details: 'Neural Agent #2 flagged non-matching transaction logs vs scale sensors.'
    }
  ];

  const filteredEvents = streamEvents.filter(ev => {
    if (streamFilter === 'all') return true;
    return ev.type === streamFilter;
  });

  return (
    <div className="space-y-6 pb-12 relative animate-fadeIn">
      {/* Dynamic Keyframe & Pulse Styles */}
      <style>{`
        @keyframes pulseGlow {
          0%, 100% { opacity: 0.85; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.05); }
        }
        @keyframes flowDash {
          to { stroke-dashoffset: -40; }
        }
        .flow-line {
          stroke-dasharray: 6 6;
          animation: flowDash 3s linear infinite;
        }
      `}</style>

      {/* Floating Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-[200] bg-slate-900/95 backdrop-blur-md text-white px-5 py-3 rounded-2xl shadow-2xl shadow-black/30 border border-slate-700 flex items-center gap-3 animate-slideUp">
          <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />
          <span className="text-xs font-semibold">{toast}</span>
        </div>
      )}

      {/* =========================================================================
          1. HEADER & LIVE TELEMETRY OPERATIONS BAR
         ========================================================================= */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-white/75 backdrop-blur-xl border border-white/80 p-5 rounded-3xl shadow-xl shadow-emerald-950/5 relative overflow-hidden">
        {/* Ambient Gradient Glow */}
        <div className="absolute -top-12 -right-12 w-72 h-72 bg-gradient-to-br from-emerald-400/15 via-teal-400/10 to-transparent rounded-full blur-3xl pointer-events-none" />

        <div className="space-y-1 relative z-10">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold tracking-wider uppercase bg-gradient-to-r from-[#062d22] to-[#14654a] text-white shadow-sm shadow-emerald-900/30">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              Live Telemetry Grid Active
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-800 border border-emerald-500/20">
              <Radio size={12} className="text-emerald-600 animate-pulse" />
              DEFCON 4 • Grid Nominal
            </span>
            <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full border border-slate-200">
              {currentTime || '12:00:00 IST'}
            </span>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight flex items-center gap-3">
            Command Center
            <span className="text-xs font-normal text-slate-600 bg-slate-100/90 px-2.5 py-0.5 rounded-md border border-slate-200/80">
              Mission Control v4.8
            </span>
          </h1>
          <p className="text-xs md:text-sm text-slate-500">
            Real-time surveillance of central grain reserves, multi-agent AI detectors, and 414 Fair Price Shop distribution pipelines.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5 relative z-10">
          <button
            onClick={() => setEmergencyModalOpen(true)}
            className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl text-xs font-bold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 transition-all shadow-sm active:scale-95"
          >
            <Lock size={14} className="text-rose-600" />
            Emergency Protocol
          </button>

          <button
            onClick={() => setIsStreaming(!isStreaming)}
            className={`flex items-center gap-2 px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all shadow-sm active:scale-95 border ${
              isStreaming 
                ? 'bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200' 
                : 'bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100'
            }`}
          >
            {isStreaming ? <Pause size={14} /> : <Play size={14} />}
            {isStreaming ? 'Pause Stream' : 'Resume Stream'}
          </button>

          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-[#062d22] via-[#14654a] to-[#2fa56f] hover:opacity-95 transition-all shadow-md shadow-emerald-950/20 active:scale-95"
          >
            <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
            Sync Grid
          </button>
        </div>
      </div>

      {/* =========================================================================
          2. FOUR ULTRA-LUXURY GRADIENT TELEMETRY KPI CARDS
         ========================================================================= */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: System Throughput (Hero Emerald Gradient) */}
        <div 
          onClick={() => onNavigate('inventory')}
          className="relative group cursor-pointer overflow-hidden rounded-3xl p-5 bg-gradient-to-br from-[#062d22] via-[#0f4f39] to-[#1a704e] text-white shadow-xl shadow-emerald-950/25 border border-emerald-400/20 hover:scale-[1.02] transition-all duration-300"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-400/10 rounded-full blur-2xl group-hover:scale-150 transition-all" />
          <div className="flex items-start justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-200/90">
              System Outflow Today
            </span>
            <div className="w-8 h-8 rounded-xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-emerald-300 group-hover:rotate-12 transition-transform">
              <Boxes size={16} />
            </div>
          </div>

          <div className="mt-3">
            <div className="text-3xl font-extrabold tracking-tight">
              43,450.5 <span className="text-lg font-medium text-emerald-200">kg</span>
            </div>
            <p className="text-xs text-emerald-200/80 mt-1 flex items-center gap-1 font-medium">
              <ArrowUpRight size={13} className="text-emerald-300" />
              +12.4% above seasonal benchmark
            </p>
          </div>

          {/* Progress Mini Bar */}
          <div className="mt-4 pt-3 border-t border-emerald-500/30">
            <div className="flex justify-between text-[11px] font-semibold text-emerald-200 mb-1.5">
              <span>Today's Quota Pacing</span>
              <span>88.2%</span>
            </div>
            <div className="w-full h-2 rounded-full bg-black/25 overflow-hidden p-0.5">
              <div 
                className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-300 transition-all duration-1000"
                style={{ width: '88.2%' }}
              />
            </div>
          </div>
        </div>

        {/* Card 2: Autonomous Neural Sentinels */}
        <div 
          onClick={() => onNavigate('analysis')}
          className="relative group cursor-pointer overflow-hidden rounded-3xl p-5 bg-white/80 backdrop-blur-xl border border-white/80 shadow-xl shadow-slate-900/5 hover:border-emerald-500/50 hover:scale-[1.02] transition-all duration-300"
        >
          <div className="flex items-start justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Autonomous AI Sentinels
            </span>
            <div className="w-8 h-8 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-700 group-hover:scale-110 transition-transform">
              <Cpu size={16} />
            </div>
          </div>

          <div className="mt-3">
            <div className="text-3xl font-extrabold text-slate-900 tracking-tight flex items-baseline gap-2">
              4 / 4
              <span className="text-xs font-bold text-emerald-700 bg-emerald-100/80 px-2 py-0.5 rounded-full border border-emerald-300">
                Active 100%
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Zero processing lag • 1,248 daily audits
            </p>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] font-semibold text-slate-600">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Timing, Stock, Volume, KYC
            </span>
            <ArrowRight size={14} className="text-slate-400 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>

        {/* Card 3: POS Terminals & Fair Price Shops */}
        <div 
          onClick={() => onNavigate('distribution')}
          className="relative group cursor-pointer overflow-hidden rounded-3xl p-5 bg-white/80 backdrop-blur-xl border border-white/80 shadow-xl shadow-slate-900/5 hover:border-blue-500/50 hover:scale-[1.02] transition-all duration-300"
        >
          <div className="flex items-start justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              FPS Outlets Connected
            </span>
            <div className="w-8 h-8 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-700 group-hover:scale-110 transition-transform">
              <Store size={16} />
            </div>
          </div>

          <div className="mt-3">
            <div className="text-3xl font-extrabold text-slate-900 tracking-tight flex items-baseline gap-2">
              402
              <span className="text-sm font-semibold text-slate-500">/ 414</span>
            </div>
            <p className="text-xs text-blue-700 font-medium mt-1 flex items-center gap-1">
              <CheckCircle2 size={13} />
              97.1% real-time POS synchrony
            </p>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] font-semibold text-slate-600">
            <span className="text-slate-500">12 Standby (Off-grid cached)</span>
            <ArrowRight size={14} className="text-slate-400 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>

        {/* Card 4: Security Threat Matrix */}
        <div 
          onClick={() => onNavigate('alerts')}
          className="relative group cursor-pointer overflow-hidden rounded-3xl p-5 bg-white/80 backdrop-blur-xl border border-white/80 shadow-xl shadow-slate-900/5 hover:border-rose-400/60 hover:scale-[1.02] transition-all duration-300"
        >
          <div className="flex items-start justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Active Security Alerts
            </span>
            <div className="w-8 h-8 rounded-xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600 group-hover:scale-110 transition-transform">
              <ShieldAlert size={16} />
            </div>
          </div>

          <div className="mt-3">
            <div className="text-3xl font-extrabold text-slate-900 tracking-tight flex items-baseline gap-2">
              5
              <span className="text-xs font-bold text-rose-700 bg-rose-100 px-2 py-0.5 rounded-full border border-rose-200">
                Critical Review
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              2 ghost duplicates, 3 inventory drops
            </p>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] font-semibold text-rose-600">
            <span className="flex items-center gap-1 font-bold">
              <AlertTriangle size={13} />
              Immediate audit required
            </span>
            <ArrowRight size={14} className="text-slate-400 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>
      </div>

      {/* =========================================================================
          3. MOTION GRAPHIC: INTERACTIVE NATIONAL SUPPLY PIPELINE & TOPOLOGY
         ========================================================================= */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Interactive Visual Network Topology (7 cols) */}
        <div className="lg:col-span-7 bg-white/80 backdrop-blur-xl border border-white/80 rounded-3xl p-5 md:p-6 shadow-xl shadow-emerald-950/5 flex flex-col justify-between relative overflow-hidden">
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-100 relative z-10">
            <div>
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
                <h3 className="text-base font-bold text-slate-900 tracking-tight">
                  National Food Security Supply Pipeline Map
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Interactive real-time transit telemetry between Central Godowns, Buffer Corridors, and Fair Price Shops.
              </p>
            </div>
            <span className="text-[11px] font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full">
              4 Logistics Convoys Active
            </span>
          </div>

          {/* SVG Motion Topology Graph */}
          <div className="relative my-4 w-full h-[320px] bg-gradient-to-b from-slate-900 via-[#062017] to-[#04150f] rounded-2xl p-4 shadow-inner overflow-hidden border border-emerald-900/40">
            {/* Grid background lines */}
            <div 
              className="absolute inset-0 opacity-15 pointer-events-none"
              style={{
                backgroundImage: `radial-gradient(circle at 1px 1px, #2fa56f 1px, transparent 0)`,
                backgroundSize: '24px 24px'
              }}
            />

            <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
              <defs>
                <linearGradient id="pipeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.8" />
                </linearGradient>
              </defs>

              {/* Connecting Supply Vectors with animated flow */}
              <line x1="50" y1="20" x2="20" y2="55" stroke="rgba(47, 165, 111, 0.3)" strokeWidth="1" />
              <line x1="50" y1="20" x2="20" y2="55" stroke="url(#pipeGrad)" strokeWidth="1.2" className="flow-line" />

              <line x1="50" y1="20" x2="40" y2="60" stroke="rgba(47, 165, 111, 0.3)" strokeWidth="1" />
              <line x1="50" y1="20" x2="40" y2="60" stroke="url(#pipeGrad)" strokeWidth="1.2" className="flow-line" />

              <line x1="50" y1="20" x2="65" y2="55" stroke="rgba(47, 165, 111, 0.3)" strokeWidth="1" />
              <line x1="50" y1="20" x2="65" y2="55" stroke="url(#pipeGrad)" strokeWidth="1.2" className="flow-line" />

              <line x1="50" y1="20" x2="82" y2="65" stroke="rgba(47, 165, 111, 0.3)" strokeWidth="1" />
              <line x1="50" y1="20" x2="82" y2="65" stroke="url(#pipeGrad)" strokeWidth="1.2" className="flow-line" />

              <line x1="20" y1="55" x2="50" y2="90" stroke="rgba(47, 165, 111, 0.2)" strokeWidth="0.8" />
              <line x1="40" y1="60" x2="50" y2="90" stroke="rgba(47, 165, 111, 0.2)" strokeWidth="0.8" />
              <line x1="65" y1="55" x2="50" y2="90" stroke="rgba(47, 165, 111, 0.2)" strokeWidth="0.8" />
              <line x1="82" y1="65" x2="50" y2="90" stroke="rgba(47, 165, 111, 0.2)" strokeWidth="0.8" />
              
              <line x1="40" y1="60" x2="50" y2="90" stroke="#38bdf8" strokeWidth="1" className="flow-line" />
              <line x1="65" y1="55" x2="50" y2="90" stroke="#fbbf24" strokeWidth="1" className="flow-line" />
            </svg>

            {/* Clickable Node Overlays */}
            {networkNodes.map(node => {
              const isSelected = selectedNodeId === node.id;
              return (
                <button
                  key={node.id}
                  onClick={() => setSelectedNodeId(node.id)}
                  style={{ left: `${node.x}%`, top: `${node.y}%` }}
                  className={`absolute -translate-x-1/2 -translate-y-1/2 p-2 rounded-2xl flex items-center gap-2 transition-all duration-300 focus:outline-none ${
                    isSelected 
                      ? 'bg-emerald-500/30 border-2 border-emerald-300 text-white shadow-lg shadow-emerald-500/50 scale-110 z-20 backdrop-blur-md' 
                      : 'bg-black/60 hover:bg-black/80 border border-emerald-500/40 text-slate-200 hover:scale-105 z-10 backdrop-blur-sm'
                  }`}
                >
                  <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center ${
                    node.type === 'central' 
                      ? 'bg-emerald-400 animate-pulse' 
                      : node.status === 'warning' 
                      ? 'bg-amber-400' 
                      : 'bg-teal-400'
                  }`}>
                    <div className="w-1.5 h-1.5 rounded-full bg-slate-900" />
                  </div>
                  <span className="text-[11px] font-bold tracking-wide whitespace-nowrap hidden sm:inline">
                    {node.name.split('(')[0].trim()}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Map Footer Legend */}
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500 pt-2 border-t border-slate-100">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                Central Apex
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-teal-400" />
                Regional Buffer
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                Surge Load
              </span>
            </div>
            <span className="text-[11px] font-mono text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
              Click any node to inspect telemetry
            </span>
          </div>
        </div>

        {/* Selected Node Telemetry Dossier (5 cols) */}
        <div className="lg:col-span-5 bg-gradient-to-br from-slate-900 via-[#0a231a] to-[#04160f] text-white rounded-3xl p-6 shadow-xl shadow-emerald-950/20 border border-emerald-800/40 flex flex-col justify-between relative overflow-hidden">
          {/* Ambient Glow */}
          <div className="absolute top-0 right-0 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

          <div>
            <div className="flex items-center justify-between pb-3 border-b border-emerald-800/40">
              <div className="flex items-center gap-2">
                <Warehouse size={16} className="text-emerald-400" />
                <span className="text-[11px] font-mono tracking-wider uppercase text-emerald-300">
                  Node Telemetry Dossier
                </span>
              </div>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                selectedNode.status === 'nominal' 
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' 
                  : selectedNode.status === 'warning'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  : 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
              }`}>
                {selectedNode.status}
              </span>
            </div>

            <h4 className="text-xl font-extrabold text-white mt-4 tracking-tight">
              {selectedNode.name}
            </h4>
            <p className="text-xs text-slate-400 mt-0.5">
              {selectedNode.location}
            </p>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-3 mt-5">
              <div className="p-3.5 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">
                  Current Reserve
                </span>
                <span className="text-lg font-bold text-emerald-300 mt-1 block">
                  {selectedNode.stock}
                </span>
                <span className="text-[10px] text-slate-400">
                  Max: {selectedNode.capacity}
                </span>
              </div>

              <div className="p-3.5 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">
                  Outflow Velocity
                </span>
                <span className="text-lg font-bold text-teal-300 mt-1 block">
                  {selectedNode.throughput}
                </span>
                <span className="text-[10px] text-slate-400">
                  Paced for peak hours
                </span>
              </div>

              <div className="p-3.5 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">
                  Active Convoys
                </span>
                <span className="text-lg font-bold text-white mt-1 block flex items-center gap-1.5">
                  <Truck size={16} className="text-emerald-400" />
                  {selectedNode.activeTrucks} Trucks
                </span>
                <span className="text-[10px] text-emerald-400/80">
                  GPS Telematics Online
                </span>
              </div>

              <div className="p-3.5 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block">
                  Security Integrity
                </span>
                <span className="text-lg font-bold text-emerald-400 mt-1 block flex items-center gap-1.5">
                  <ShieldCheck size={16} className="text-emerald-400" />
                  100% Tamper-Free
                </span>
                <span className="text-[10px] text-slate-400">
                  RFID Weight Verified
                </span>
              </div>
            </div>
          </div>

          {/* Quick Hub Navigation Link */}
          <div className="mt-6 pt-4 border-t border-emerald-800/40 flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Manage inventory consignment records
            </span>
            <button
              onClick={() => onNavigate('inventory')}
              className="flex items-center gap-1.5 text-xs font-bold text-emerald-300 hover:text-white transition-colors"
            >
              Open Silo Inventory
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* =========================================================================
          4. LIVE TELEMETRY LOGS & REAL-TIME INCIDENT FEED
         ========================================================================= */}
      <div className="bg-white/80 backdrop-blur-xl border border-white/80 rounded-3xl p-5 md:p-6 shadow-xl shadow-emerald-950/5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <Activity size={18} className="text-emerald-700" />
              <h3 className="text-base font-bold text-slate-900 tracking-tight">
                Live Distribution & Security Telemetry Stream
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Continuous transaction log verifying Aadhaar iris biometrics, consignment waybills, and neural sentinel flags.
            </p>
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1.5 bg-slate-100/90 p-1 rounded-2xl border border-slate-200 self-start sm:self-auto">
            {(['all', 'dispatch', 'security', 'inventory'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setStreamFilter(tab)}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold capitalize transition-all ${
                  streamFilter === tab
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {/* Streaming Event Items */}
        <div className="divide-y divide-slate-100 mt-2">
          {filteredEvents.map(event => (
            <div 
              key={event.id}
              className="py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:bg-slate-50/70 p-3 rounded-2xl transition-colors group"
            >
              <div className="flex items-start gap-3">
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${
                  event.type === 'security'
                    ? 'bg-rose-50 text-rose-600 border border-rose-200'
                    : event.type === 'inventory'
                    ? 'bg-blue-50 text-blue-600 border border-blue-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}>
                  {event.type === 'security' && <ShieldAlert size={17} />}
                  {event.type === 'inventory' && <Warehouse size={17} />}
                  {event.type === 'dispatch' && <Store size={17} />}
                </div>

                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <h5 className="text-xs md:text-sm font-bold text-slate-800 group-hover:text-emerald-900 transition-colors">
                      {event.title}
                    </h5>
                    <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded-md border ${event.badgeColor}`}>
                      {event.badge}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 font-medium">
                    {event.subtitle}
                  </p>
                  <p className="text-xs text-slate-600">
                    {event.details}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0 self-end md:self-center">
                <span className="text-[11px] font-mono text-slate-400">
                  {event.timestamp}
                </span>
                <button
                  onClick={() => {
                    if (event.type === 'security') onNavigate('alerts');
                    else if (event.type === 'inventory') onNavigate('inventory');
                    else onNavigate('distribution');
                  }}
                  className="text-xs font-bold text-slate-700 hover:text-emerald-700 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-xl transition-all"
                >
                  Audit Record
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* =========================================================================
          5. OPERATIONS COMMAND HUB (6 INTERACTIVE GLASS NAVIGATION MODULES)
         ========================================================================= */}
      <div>
        <div className="flex items-center justify-between mb-4 px-1">
          <div>
            <h3 className="text-base font-bold text-slate-900 tracking-tight">
              Operational Command Subsystems
            </h3>
            <p className="text-xs text-slate-500">
              Direct access channels to national food distribution infrastructure modules.
            </p>
          </div>
          <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
            All 6 Subsystems Synchronized
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Subsystem 1: AI Analysis */}
          <div
            onClick={() => onNavigate('analysis')}
            className="group cursor-pointer p-5 rounded-3xl bg-white/80 backdrop-blur-xl border border-white/80 shadow-lg shadow-emerald-950/5 hover:border-emerald-500/40 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-[#062d22] to-[#14654a] text-white flex items-center justify-center shadow-md shadow-emerald-950/20 group-hover:scale-110 transition-transform">
                <Cpu size={20} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900 group-hover:text-emerald-800 transition-colors">
                  Autonomous AI Sentinels
                </h4>
                <p className="text-xs text-slate-500 mt-1">
                  Multi-agent anomaly detection pipeline with real-time audit terminal, case dossier inspector, and risk scoring.
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-bold text-emerald-700">
              <span>Launch Sentinel Console</span>
              <ArrowRight size={14} className="group-hover:translate-x-1.5 transition-transform" />
            </div>
          </div>

          {/* Subsystem 2: Inventory */}
          <div
            onClick={() => onNavigate('inventory')}
            className="group cursor-pointer p-5 rounded-3xl bg-white/80 backdrop-blur-xl border border-white/80 shadow-lg shadow-emerald-950/5 hover:border-emerald-500/40 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-emerald-600 to-teal-700 text-white flex items-center justify-center shadow-md shadow-emerald-950/20 group-hover:scale-110 transition-transform">
                <Warehouse size={20} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900 group-hover:text-emerald-800 transition-colors">
                  Central Buffer Silos
                </h4>
                <p className="text-xs text-slate-500 mt-1">
                  Manage Rice, Wheat, Sugar, and Kerosene reserves, log FCI challan inflows, and replenish low-stock outlets.
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-bold text-emerald-700">
              <span>View Reserve Inventory</span>
              <ArrowRight size={14} className="group-hover:translate-x-1.5 transition-transform" />
            </div>
          </div>

          {/* Subsystem 3: Beneficiaries */}
          <div
            onClick={() => onNavigate('beneficiaries')}
            className="group cursor-pointer p-5 rounded-3xl bg-white/80 backdrop-blur-xl border border-white/80 shadow-lg shadow-emerald-950/5 hover:border-emerald-500/40 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white flex items-center justify-center shadow-md shadow-blue-950/20 group-hover:scale-110 transition-transform">
                <Users size={20} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900 group-hover:text-blue-800 transition-colors">
                  Citizen Ration Registry
                </h4>
                <p className="text-xs text-slate-500 mt-1">
                  Verify NFSA ration cardholders, manage AAY/PHH welfare allocations, and enforce Aadhaar KYC verification.
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-bold text-blue-700">
              <span>Inspect Beneficiaries</span>
              <ArrowRight size={14} className="group-hover:translate-x-1.5 transition-transform" />
            </div>
          </div>

          {/* Subsystem 4: Analytics */}
          <div
            onClick={() => onNavigate('analytics')}
            className="group cursor-pointer p-5 rounded-3xl bg-white/80 backdrop-blur-xl border border-white/80 shadow-lg shadow-emerald-950/5 hover:border-emerald-500/40 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-teal-600 to-emerald-700 text-white flex items-center justify-center shadow-md shadow-teal-950/20 group-hover:scale-110 transition-transform">
                <BarChart3 size={20} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900 group-hover:text-teal-800 transition-colors">
                  Dynamic Supply Analytics
                </h4>
                <p className="text-xs text-slate-500 mt-1">
                  Compare stock withdrawal curves vs silo availability with dual-axis curves, burn rates, and commodity filters.
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-bold text-teal-700">
              <span>Explore Analytics Curves</span>
              <ArrowRight size={14} className="group-hover:translate-x-1.5 transition-transform" />
            </div>
          </div>

          {/* Subsystem 5: Alerts */}
          <div
            onClick={() => onNavigate('alerts')}
            className="group cursor-pointer p-5 rounded-3xl bg-white/80 backdrop-blur-xl border border-white/80 shadow-lg shadow-emerald-950/5 hover:border-rose-400/50 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-rose-600 to-red-700 text-white flex items-center justify-center shadow-md shadow-rose-950/20 group-hover:scale-110 transition-transform">
                <Bell size={20} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900 group-hover:text-rose-800 transition-colors">
                  Security Alert Center
                </h4>
                <p className="text-xs text-slate-500 mt-1">
                  Manage 5 active security incidents, assign inspection officers, and block flagged fraudulent biometric attempts.
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-bold text-rose-700">
              <span>Review 5 Active Flags</span>
              <ArrowRight size={14} className="group-hover:translate-x-1.5 transition-transform" />
            </div>
          </div>

          {/* Subsystem 6: Reports */}
          <div
            onClick={() => onNavigate('reports')}
            className="group cursor-pointer p-5 rounded-3xl bg-white/80 backdrop-blur-xl border border-white/80 shadow-lg shadow-emerald-950/5 hover:border-emerald-500/40 hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between"
          >
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-slate-700 to-slate-900 text-white flex items-center justify-center shadow-md shadow-slate-950/20 group-hover:scale-110 transition-transform">
                <FileText size={20} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-900 group-hover:text-slate-800 transition-colors">
                  Compliance Dossiers
                </h4>
                <p className="text-xs text-slate-500 mt-1">
                  Official government NFSA compliance audits, certified PDF dispatches, and custom dossier compiler wizard.
                </p>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs font-bold text-slate-800">
              <span>Access Compliance Suite</span>
              <ArrowRight size={14} className="group-hover:translate-x-1.5 transition-transform" />
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
          6. EMERGENCY OVERRIDE & ALLOCATION LOCKDOWN MODAL (PORTALED)
         ========================================================================= */}
      {emergencyModalOpen && createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-md animate-fadeIn">
          <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 max-w-lg w-full overflow-hidden animate-scaleUp">
            {/* Modal Header */}
            <div className="p-6 bg-gradient-to-r from-rose-700 to-red-800 text-white flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20">
                  <ShieldAlert size={22} className="text-rose-200" />
                </div>
                <div>
                  <h3 className="text-lg font-bold">Emergency Operations Protocol</h3>
                  <p className="text-xs text-rose-200">National Food Security Grid Override</p>
                </div>
              </div>
              <button 
                onClick={() => setEmergencyModalOpen(false)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4">
              <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 text-xs space-y-1">
                <div className="font-bold flex items-center gap-1.5 text-rose-800">
                  <AlertTriangle size={15} />
                  Elevated Authorization Required
                </div>
                <p>
                  Initiating an emergency lockdown will freeze all off-schedule FPS dispatches, enforce strict multi-factor biometric reverification on all 414 POS terminals, and notify district magistrates.
                </p>
              </div>

              <div className="space-y-3">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                  Select Emergency Protocol
                </label>
                <div className="space-y-2">
                  <label className="flex items-start gap-3 p-3 rounded-2xl border border-slate-200 hover:bg-slate-50 cursor-pointer transition-all">
                    <input type="radio" name="protocol" defaultChecked className="mt-0.5 accent-rose-600" />
                    <div>
                      <span className="text-xs font-bold text-slate-900 block">Divert Emergency Stock to Drought Zones</span>
                      <span className="text-[11px] text-slate-500">Auto-routes 150,000 kg buffer grain from FCI Godown #12 to designated relief camps.</span>
                    </div>
                  </label>

                  <label className="flex items-start gap-3 p-3 rounded-2xl border border-slate-200 hover:bg-slate-50 cursor-pointer transition-all">
                    <input type="radio" name="protocol" className="mt-0.5 accent-rose-600" />
                    <div>
                      <span className="text-xs font-bold text-slate-900 block">Full FPS Terminal Lockout (Fraud Contagion)</span>
                      <span className="text-[11px] text-slate-500">Instantly locks out POS terminals flagged with anomalous iris scan replay attacks.</span>
                    </div>
                  </label>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-6 bg-slate-50 border-t border-slate-100 flex items-center justify-end gap-3">
              <button
                onClick={() => setEmergencyModalOpen(false)}
                className="px-4 py-2.5 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-200 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setEmergencyModalOpen(false);
                  triggerToast('Emergency Directive broadcasted across all 414 FPS terminals.');
                }}
                className="px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 shadow-md shadow-rose-950/20 transition-all"
              >
                Confirm & Enforce Protocol
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};
