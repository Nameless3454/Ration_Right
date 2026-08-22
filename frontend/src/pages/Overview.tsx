import React, { useState } from 'react';
import { RefreshCw, Clock, ArrowRight, Play, BrainCircuit } from 'lucide-react';
import { StatCard } from '../components/StatCard';
import { AlertSummary } from '../components/AlertSummary';
import { InvestigationTable } from '../components/InvestigationTable';
import { DistributionTable } from '../components/DistributionTable';
import { mockKpis, mockInvestigations, mockDistricts, mockAlertSummary } from '../data/mockData';

interface OverviewProps {
  onSelectInvestigation: (id: string) => void;
  onNavigate: (route: string) => void;
  searchQuery: string;
}

export const Overview: React.FC<OverviewProps> = ({
  onSelectInvestigation,
  onNavigate,
  searchQuery
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState('Today, 10:24 AM');
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);

  const startAnalysis = () => {
    setIsRunning(true);
    setLogs([]);
    const messages = [
      'Initializing Agent 1: Transaction Analyst...',
      'Agent 1: Scanning database patterns...',
      'Initializing Agent 2: Anomaly Investigator...',
      'Agent 2: Verified transaction time-deltas.',
      'Initializing Agent 3: Evidence Case Builder...',
      'Agent 3: Case structured (Confidence: 94%).',
      'Initializing Agent 4: Alert Generator...',
      'Agent 4: Dashboard alert dispatches complete.'
    ];

    messages.forEach((msg, idx) => {
      setTimeout(() => {
        setLogs(prev => [...prev, msg]);
        if (idx === messages.length - 1) setIsRunning(false);
      }, (idx + 1) * 300);
    });
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
      const now = new Date();
      setLastUpdated(`Today, ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
    }, 1200);
  };

  // Filter investigations based on search query
  const filteredInvestigations = mockInvestigations.filter(inv => 
    inv.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    inv.fps.toLowerCase().includes(searchQuery.toLowerCase()) ||
    inv.district.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Filter districts based on search query
  const filteredDistricts = mockDistricts.filter(dist =>
    dist.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">Overview</h1>
          <p className="text-xs md:text-sm text-slate-500 mt-1">
            Monitor ration distribution, inventory health, and AI-detected operational risks.
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="self-start sm:self-center flex items-center justify-center gap-1.5 px-3 py-1.5 border border-slate-200 bg-white hover:bg-slate-50 rounded text-xs font-semibold text-slate-700 disabled:opacity-50 transition-colors"
        >
          <RefreshCw size={14} className={isRefreshing ? 'animate-spin' : ''} />
          <span>{isRefreshing ? 'Updating...' : 'Refresh'}</span>
        </button>
      </div>

      {/* System Status Card */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 md:p-5 flex flex-wrap items-center gap-x-12 gap-y-4">
        <div className="flex items-center gap-3">
          <span className="w-1.5 h-1.5 rounded-full bg-[#0284C7] shrink-0"></span>
          <div>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Data Status</span>
            <span className="text-xs md:text-sm font-bold text-slate-800">Recent</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="w-1.5 h-1.5 rounded-full bg-[#0284C7] shrink-0"></span>
          <div>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">AI Workflow</span>
            <span className="text-xs md:text-sm font-bold text-slate-800">Operational</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Clock size={16} className="text-slate-400 shrink-0" />
          <div>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Last Updated</span>
            <span className="text-xs md:text-sm font-bold text-slate-800">{lastUpdated}</span>
          </div>
        </div>

        <div className="ml-auto">
          <button 
            onClick={() => onNavigate('settings')}
            className="px-3 py-1 border border-slate-200 hover:bg-slate-50 rounded text-xs font-semibold text-slate-600 transition-colors"
          >
            Details
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Total Beneficiaries"
          value={mockKpis.beneficiaries.value.toLocaleString()}
          change={mockKpis.beneficiaries.change}
          text={mockKpis.beneficiaries.text}
          sub={mockKpis.beneficiaries.sub}
          iconName="Users"
          iconColor="#0369A1"
          iconBg="#F0F9FF"
        />
        <StatCard
          title="Ration Distributed"
          value={`${mockKpis.distributed.value.toLocaleString()} kg`}
          change={mockKpis.distributed.change}
          text={mockKpis.distributed.text}
          sub={mockKpis.distributed.sub}
          iconName="ShoppingBag"
          iconColor="#0369A1"
          iconBg="#F0F9FF"
        />
        <StatCard
          title="Total Inventory"
          value={`${mockKpis.inventory.value.toLocaleString()} kg`}
          change={mockKpis.inventory.change}
          text={mockKpis.inventory.text}
          sub={mockKpis.inventory.sub}
          iconName="Database"
          iconColor="#0369A1"
          iconBg="#F0F9FF"
        />
        <StatCard
          title="Active Alerts"
          value={mockKpis.alerts.value}
          change={mockKpis.alerts.change}
          text={mockKpis.alerts.text}
          sub={mockKpis.alerts.sub}
          iconName="Bell"
          iconColor="#C2410C"
          iconBg="#FFF7ED"
        />
        <StatCard
          title="High-Risk Cases"
          value={mockKpis.highRisk.value}
          change={mockKpis.highRisk.change}
          text={mockKpis.highRisk.text}
          sub={mockKpis.highRisk.sub}
          iconName="Shield"
          iconColor="#991B1B"
          iconBg="#FEF2F2"
        />
      </div>

      {/* Two Column Table Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Table: Investigations */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 lg:col-span-7 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-slate-800 text-sm md:text-base">Recent Investigations</h3>
              <p className="text-xs text-slate-400 mt-0.5">Latest detected anomalies and findings</p>
            </div>
            <button
              onClick={() => onNavigate('alerts')}
              className="flex items-center gap-0.5 text-xs font-semibold text-[#0284C7] hover:text-[#0369A1] transition-colors"
            >
              View all <ArrowRight size={13} />
            </button>
          </div>
          <InvestigationTable 
            investigations={filteredInvestigations.slice(0, 5)} 
            onRowClick={onSelectInvestigation} 
          />
        </div>

        {/* Right Table: Distribution Overview */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 lg:col-span-5 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-slate-800 text-sm md:text-base">Distribution Overview</h3>
              <p className="text-xs text-slate-400 mt-0.5">Activity across districts</p>
            </div>
            <button
              onClick={() => onNavigate('distribution')}
              className="flex items-center gap-0.5 text-xs font-semibold text-[#0284C7] hover:text-[#0369A1] transition-colors"
            >
              View all <ArrowRight size={13} />
            </button>
          </div>
          <DistributionTable districts={filteredDistricts.slice(0, 5)} />
        </div>
      </div>

      {/* Two Column Detail/Summary Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Component: Alert Summary */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 lg:col-span-7 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-slate-800 text-sm md:text-base">Alert Summary</h3>
              <p className="text-xs text-slate-400 mt-0.5">Active alerts by severity</p>
            </div>
            <button
              onClick={() => onNavigate('alerts')}
              className="flex items-center gap-0.5 text-xs font-semibold text-[#0284C7] hover:text-[#0369A1] transition-colors"
            >
              View all <ArrowRight size={13} />
            </button>
          </div>
          <AlertSummary
            critical={mockAlertSummary.critical}
            high={mockAlertSummary.high}
            medium={mockAlertSummary.medium}
            low={mockAlertSummary.low}
            onSelectSeverity={() => {
              onNavigate('alerts');
            }}
          />
        </div>

        {/* Right Component: AI Analysis */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 lg:col-span-5 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-slate-800 text-sm md:text-base">AI Analysis</h3>
              <p className="text-xs text-slate-400 mt-0.5">Execute and monitor agent pipeline runs</p>
            </div>
            <button
              onClick={() => onNavigate('analysis')}
              className="flex items-center gap-0.5 text-xs font-semibold text-[#0284C7] hover:text-[#0369A1] transition-colors"
            >
              View all <ArrowRight size={13} />
            </button>
          </div>

          <div className="flex flex-col gap-3">
            <button
              onClick={startAnalysis}
              disabled={isRunning}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-[#0284C7] hover:bg-[#0369A1] disabled:opacity-50 text-white text-xs font-bold rounded shadow-xs transition-colors"
            >
              <Play size={14} />
              <span>{isRunning ? 'Running agents...' : 'Trigger Analysis Run'}</span>
            </button>

            {logs.length > 0 ? (
              <div className="bg-slate-900 font-mono text-[10px] text-slate-300 p-3 rounded-lg space-y-1 h-36 overflow-y-auto border border-slate-800">
                {logs.map((log, i) => (
                  <div key={i} className="flex items-center gap-1.5">
                    <span className="text-[#0284C7] font-bold">&gt;</span>
                    <span>{log}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="border border-slate-100 bg-slate-50/50 rounded-lg p-6 text-center text-xs text-slate-400 flex flex-col items-center justify-center gap-2 h-36">
                <BrainCircuit size={20} className="text-slate-300" />
                <span>Ready to trigger the multi-agent detection pipeline.</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
