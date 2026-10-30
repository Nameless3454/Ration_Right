import React, { useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { 
  ShieldAlert, 
  AlertTriangle, 
  AlertCircle, 
  CheckCircle2, 
  Search, 
  FileDown, 
  Check, 
  X, 
  Radio, 
  ArrowRight, 
  MapPin, 
  Clock, 
  ChevronDown, 
  Bell,
  ShieldCheck,
  Activity,
  Zap,
  Lock
} from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { mockAlerts as initialAlerts } from '../data/mockData';
import { Alert as AlertType } from '../types';

export const Alerts: React.FC = () => {
  // Rich Alerts Dataset
  const extendedAlerts: AlertType[] = useMemo(() => [
    ...initialAlerts,
    {
      id: 'ALT-107',
      title: 'Off-Hours POS Transaction Burst',
      severity: 'Critical',
      status: 'Open',
      createdAt: '2026-08-09 23:45',
      fps: 'FPS-AB-0099',
      district: 'Aurangabad',
      description: '42 consecutive biometric transactions verified between 23:30 and 23:55 when center is legally closed.'
    },
    {
      id: 'ALT-108',
      title: 'Quota Balance Deviation Discrepancy',
      severity: 'High',
      status: 'Open',
      createdAt: '2026-08-09 14:15',
      fps: 'FPS-GW-0104',
      district: 'Gwalior',
      description: 'Central Godown dispatch logs indicate 1,200kg Rice delivered, but terminal registered only 800kg.'
    },
    {
      id: 'ALT-109',
      title: 'Biometric Scanner Failure Frequency',
      severity: 'Medium',
      status: 'Acknowledged',
      createdAt: '2026-08-08 16:20',
      fps: 'FPS-DL-0021',
      district: 'Delhi',
      description: 'Excessive OTP override requests triggered (>35% of total cardholders) bypassing optical fingerprint reader.'
    },
    {
      id: 'ALT-110',
      title: 'Scheduled Calibration Due',
      severity: 'Low',
      status: 'Resolved',
      createdAt: '2026-08-07 10:00',
      fps: 'FPS-LU-0012',
      district: 'Lucknow',
      description: 'Electronic weigh scale periodic ISO-9001 certification check due within 7 days.'
    }
  ], []);

  const [alertsList, setAlertsList] = useState<AlertType[]>(extendedAlerts);
  const [activeTab, setActiveTab] = useState<'All' | 'Critical' | 'High' | 'Medium' | 'Low'>('All');
  const [statusFilter, setStatusFilter] = useState<'All' | 'Open' | 'Acknowledged' | 'Resolved'>('All');
  const [districtFilter, setDistrictFilter] = useState('All');
  const [search, setSearch] = useState('');
  const [selectedAlert, setSelectedAlert] = useState<AlertType | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isSimulatingPing, setIsSimulatingPing] = useState(false);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleSimulateAlert = () => {
    setIsSimulatingPing(true);
    setTimeout(() => {
      const newAlert: AlertType = {
        id: `ALT-${Math.floor(111 + Math.random() * 888)}`,
        title: 'Geofence Breach: Distant Terminal Sync',
        severity: 'Critical',
        status: 'Open',
        createdAt: 'Just now',
        fps: 'BENX1',
        district: 'East Delhi',
        description: 'Biometric authorization attempted 4.2 km outside registered Fair Price Shop geofence boundary.'
      };
      setAlertsList(prev => [newAlert, ...prev]);
      setIsSimulatingPing(false);
      showToast('⚡ Live Anomaly Ping Received: Geofence breach detected at East Delhi (BENX1)!');
    }, 800);
  };

  const handleUpdateStatus = (id: string, newStatus: 'Open' | 'Acknowledged' | 'Resolved') => {
    setAlertsList(prev => prev.map(a => a.id === id ? { ...a, status: newStatus } : a));
    if (selectedAlert?.id === id) {
      setSelectedAlert(prev => prev ? { ...prev, status: newStatus } : null);
    }
    showToast(`Alert #${id} status updated to ${newStatus}.`);
  };

  const handleExportCSV = () => {
    const headers = "Alert ID,Title,Severity,District,FPS Center,Status,Timestamp,Description\n";
    const rows = filteredAlerts.map(a => 
      `"${a.id}","${a.title}","${a.severity}","${a.district}","${a.fps}","${a.status}","${a.createdAt}","${a.description.replace(/"/g, '""')}"`
    ).join("\n");
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `active-alerts-dossier-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    showToast("Active alerts exported as CSV.");
  };

  // Filter calculations
  const filteredAlerts = alertsList.filter(a => {
    const matchesTab = activeTab === 'All' || a.severity === activeTab;
    const matchesStatus = statusFilter === 'All' || a.status === statusFilter;
    const matchesDistrict = districtFilter === 'All' || a.district === districtFilter;
    const matchesSearch = 
      a.title.toLowerCase().includes(search.toLowerCase()) ||
      a.fps.toLowerCase().includes(search.toLowerCase()) ||
      a.district.toLowerCase().includes(search.toLowerCase()) ||
      a.description.toLowerCase().includes(search.toLowerCase()) ||
      a.id.toLowerCase().includes(search.toLowerCase());

    return matchesTab && matchesStatus && matchesDistrict && matchesSearch;
  });

  const uniqueDistricts = ['All', ...Array.from(new Set(alertsList.map(a => a.district)))];

  // Dynamic counts
  const criticalCount = alertsList.filter(a => a.severity === 'Critical').length;
  const highCount = alertsList.filter(a => a.severity === 'High').length;
  const mediumCount = alertsList.filter(a => a.severity === 'Medium').length;
  const lowCount = alertsList.filter(a => a.severity === 'Low').length;

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
              Active Security & Policy Alerts
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase bg-red-500/15 text-red-700 border border-red-500/30 flex items-center gap-1.5 shadow-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping"></span>
              {criticalCount} Critical Active
            </span>
          </div>
          <p className="text-xs md:text-sm text-[#5d7468] mt-1 font-medium">
            Live neural surveillance, fraud triggers, and statutory PDS compliance enforcement.
          </p>
        </div>

        {/* Action Header Buttons */}
        <div className="flex items-center gap-2.5 self-start sm:self-center">
          <button
            type="button"
            onClick={handleExportCSV}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full border border-slate-200/80 bg-white/80 hover:bg-white text-xs md:text-sm font-bold text-[#10261c] shadow-xs transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          >
            <FileDown size={15} className="text-[#5d7468]" />
            <span>Export Incident Dossier</span>
          </button>

          <button
            type="button"
            onClick={handleSimulateAlert}
            disabled={isSimulatingPing}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full font-bold text-xs md:text-sm shadow-md transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] cursor-pointer !text-white text-white shrink-0"
            style={{
              background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
              color: '#ffffff',
              boxShadow: '0 8px 20px -4px rgba(20, 101, 74, 0.45)'
            }}
          >
            {isSimulatingPing ? (
              <>
                <Radio size={16} className="text-white animate-spin" />
                <span>Simulating Inflow...</span>
              </>
            ) : (
              <>
                <Zap size={16} className="text-white fill-white" />
                <span>Simulate Anomaly Ping</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Live Glowing Anomaly Ticker Ribbon */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-red-500/10 via-amber-500/8 to-emerald-500/5 border border-red-500/25 p-3 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-red-500 text-white flex items-center justify-center shrink-0 shadow-md shadow-red-500/30 animate-pulse">
            <Bell size={16} />
          </div>
          <div className="text-xs">
            <span className="font-extrabold text-red-800 uppercase tracking-wide text-[10.5px] mr-2">
              High Priority Flag:
            </span>
            <span className="text-slate-800 font-semibold">
              Ghost Beneficiary pattern flagged at East Delhi (BENX1) — multiple concurrent requests across separate terminals.
            </span>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setSelectedAlert(alertsList[0])}
          className="shrink-0 text-xs font-bold text-red-700 hover:text-red-900 bg-white/90 hover:bg-white px-3 py-1 rounded-full border border-red-200 shadow-2xs transition-all cursor-pointer flex items-center gap-1"
        >
          <span>Investigate</span>
          <ArrowRight size={12} />
        </button>
      </div>

      {/* 4 Luxury Glass KPI Cards with Glow Effects */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Critical Alerts */}
        <div 
          onClick={() => setActiveTab('Critical')}
          className={`bg-white/90 backdrop-blur-xl border rounded-[24px] p-5 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[125px] cursor-pointer ${
            activeTab === 'Critical' ? 'border-red-500 ring-2 ring-red-500/20 shadow-red-500/10' : 'border-white/90 hover:border-red-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Critical Severity</span>
            <div className="w-9 h-9 rounded-2xl bg-red-500/12 text-red-600 flex items-center justify-center shadow-xs">
              <ShieldAlert size={20} className="animate-pulse" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-red-600 font-display">
              {criticalCount}
            </span>
            <span className="text-[11px] font-bold text-red-700 bg-red-100/80 px-2.5 py-0.5 rounded-full border border-red-200">
              Immediate Action
            </span>
          </div>
        </div>

        {/* Card 2: High Alerts */}
        <div 
          onClick={() => setActiveTab('High')}
          className={`bg-white/90 backdrop-blur-xl border rounded-[24px] p-5 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[125px] cursor-pointer ${
            activeTab === 'High' ? 'border-amber-500 ring-2 ring-amber-500/20 shadow-amber-500/10' : 'border-white/90 hover:border-amber-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">High Priority</span>
            <div className="w-9 h-9 rounded-2xl bg-amber-500/15 text-amber-700 flex items-center justify-center shadow-xs">
              <AlertTriangle size={20} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-amber-600 font-display">
              {highCount}
            </span>
            <span className="text-[11px] font-bold text-amber-800 bg-amber-100/80 px-2.5 py-0.5 rounded-full border border-amber-200">
              Escalated
            </span>
          </div>
        </div>

        {/* Card 3: Medium Alerts */}
        <div 
          onClick={() => setActiveTab('Medium')}
          className={`bg-white/90 backdrop-blur-xl border rounded-[24px] p-5 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[125px] cursor-pointer ${
            activeTab === 'Medium' ? 'border-orange-500 ring-2 ring-orange-500/20 shadow-orange-500/10' : 'border-white/90 hover:border-orange-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Medium Priority</span>
            <div className="w-9 h-9 rounded-2xl bg-orange-500/15 text-orange-700 flex items-center justify-center shadow-xs">
              <AlertCircle size={20} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-orange-600 font-display">
              {mediumCount}
            </span>
            <span className="text-[11px] font-bold text-orange-800 bg-orange-100/80 px-2.5 py-0.5 rounded-full border border-orange-200">
              Reviewing
            </span>
          </div>
        </div>

        {/* Card 4: Low Alerts */}
        <div 
          onClick={() => setActiveTab('Low')}
          className={`bg-white/90 backdrop-blur-xl border rounded-[24px] p-5 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[125px] cursor-pointer ${
            activeTab === 'Low' ? 'border-emerald-500 ring-2 ring-emerald-500/20 shadow-emerald-500/10' : 'border-white/90 hover:border-emerald-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Low / Routine</span>
            <div className="w-9 h-9 rounded-2xl bg-[#14654a]/12 text-[#14654a] flex items-center justify-center shadow-xs">
              <CheckCircle2 size={20} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold text-[#14654a] font-display">
              {lowCount}
            </span>
            <span className="text-[11px] font-bold text-[#14654a] bg-emerald-100/70 px-2.5 py-0.5 rounded-full border border-emerald-200">
              Monitored
            </span>
          </div>
        </div>
      </div>

      {/* Interactive Controls & Filters Bar */}
      <div className="bg-white/90 backdrop-blur-xl border border-white/90 rounded-[28px] p-5 shadow-sm space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3.5">
          {/* Severity Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0">
            <button
              type="button"
              onClick={() => setActiveTab('All')}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer whitespace-nowrap ${
                activeTab === 'All'
                  ? 'bg-[#14654a] text-white shadow-xs'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
              }`}
            >
              All Incidents ({alertsList.length})
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('Critical')}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer whitespace-nowrap flex items-center gap-1.5 ${
                activeTab === 'Critical'
                  ? 'bg-red-600 text-white shadow-xs'
                  : 'bg-red-50 hover:bg-red-100 text-red-700'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span>
              Critical ({criticalCount})
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('High')}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer whitespace-nowrap flex items-center gap-1.5 ${
                activeTab === 'High'
                  ? 'bg-amber-600 text-white shadow-xs'
                  : 'bg-amber-50 hover:bg-amber-100 text-amber-700'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
              High ({highCount})
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('Medium')}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer whitespace-nowrap flex items-center gap-1.5 ${
                activeTab === 'Medium'
                  ? 'bg-orange-600 text-white shadow-xs'
                  : 'bg-orange-50 hover:bg-orange-100 text-orange-700'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500"></span>
              Medium ({mediumCount})
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('Low')}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer whitespace-nowrap flex items-center gap-1.5 ${
                activeTab === 'Low'
                  ? 'bg-emerald-700 text-white shadow-xs'
                  : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-800'
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              Low ({lowCount})
            </button>
          </div>

          {/* District, Status & Search Filters */}
          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Status Dropdown */}
            <div className="relative">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as any)}
                className="pl-3 pr-8 py-2 rounded-full border border-slate-200/90 bg-slate-50/80 hover:bg-white text-xs font-bold text-[#10261c] focus:outline-none focus:border-[#14654a] appearance-none cursor-pointer"
              >
                <option value="All">All Statuses</option>
                <option value="Open">Open</option>
                <option value="Acknowledged">Acknowledged</option>
                <option value="Resolved">Resolved</option>
              </select>
              <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>

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
                placeholder="Search alerts, FPS, ID..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-3.5 py-2 rounded-full border border-slate-200/90 bg-slate-50/80 hover:bg-white focus:bg-white text-xs text-[#10261c] placeholder-slate-400 focus:outline-none focus:border-[#14654a] transition-all font-medium"
              />
              {search && (
                <button 
                  onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Elevated Glass Table */}
        <div className="overflow-hidden border border-slate-100 rounded-2xl bg-white shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs md:text-sm">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-100 text-[#7a8b84] font-bold tracking-wider text-[10.5px] uppercase">
                  <th className="py-3.5 px-5">Alert ID</th>
                  <th className="py-3.5 px-5">Incident Title & Synopsis</th>
                  <th className="py-3.5 px-4 text-center">Severity</th>
                  <th className="py-3.5 px-4">District</th>
                  <th className="py-3.5 px-4">FPS Center</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4">Timestamp</th>
                  <th className="py-3.5 px-5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100/80">
                {filteredAlerts.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-xs text-slate-400">
                      <ShieldCheck size={28} className="mx-auto text-slate-300 mb-2" />
                      <p className="font-bold text-slate-700">No active incidents matching your criteria</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">All monitored fair price distribution centers are operating within baseline parameters.</p>
                    </td>
                  </tr>
                ) : (
                  filteredAlerts.map((a) => {
                    const isCritical = a.severity === 'Critical';
                    return (
                      <tr 
                        key={a.id} 
                        className={`transition-all duration-150 group hover:bg-[#f2f8f5]/60 cursor-pointer ${
                          isCritical ? 'bg-red-500/[0.02]' : ''
                        }`}
                        onClick={() => setSelectedAlert(a)}
                      >
                        {/* Alert ID */}
                        <td className="py-4 px-5">
                          <span className="font-mono font-extrabold text-xs text-[#10261c] bg-slate-100/90 group-hover:bg-white px-2.5 py-1 rounded-lg border border-slate-200/70 inline-block shadow-2xs">
                            {a.id}
                          </span>
                        </td>

                        {/* Title & Description */}
                        <td className="py-4 px-5 max-w-sm">
                          <div>
                            <div className="font-extrabold text-[#10261c] text-xs md:text-sm group-hover:text-[#14654a] transition-colors flex items-center gap-2">
                              {a.title}
                              {isCritical && (
                                <span className="w-2 h-2 rounded-full bg-red-500 animate-ping shrink-0"></span>
                              )}
                            </div>
                            <div className="text-[11px] text-[#5d7468] mt-0.5 line-clamp-1 font-medium">
                              {a.description}
                            </div>
                          </div>
                        </td>

                        {/* Severity */}
                        <td className="py-4 px-4 text-center">
                          <StatusBadge type={a.severity} text={a.severity} />
                        </td>

                        {/* District */}
                        <td className="py-4 px-4">
                          <span className="font-bold text-[#10261c] flex items-center gap-1.5 text-xs">
                            <MapPin size={12} className="text-[#14654a]" />
                            {a.district}
                          </span>
                        </td>

                        {/* FPS Center */}
                        <td className="py-4 px-4">
                          <span className="font-mono font-bold text-xs text-slate-700 bg-slate-50 px-2 py-0.5 rounded-md border border-slate-200/60">
                            {a.fps}
                          </span>
                        </td>

                        {/* Status */}
                        <td className="py-4 px-4">
                          <StatusBadge type={a.status} text={a.status} />
                        </td>

                        {/* Timestamp */}
                        <td className="py-4 px-4 text-xs text-slate-400 whitespace-nowrap">
                          <span className="flex items-center gap-1">
                            <Clock size={12} />
                            {a.createdAt}
                          </span>
                        </td>

                        {/* Action Column */}
                        <td className="py-4 px-5 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => setSelectedAlert(a)}
                              className="px-3 py-1 rounded-full text-xs font-bold text-[#14654a] bg-[#14654a]/10 hover:bg-[#14654a]/20 transition-colors cursor-pointer"
                            >
                              Inspect
                            </button>

                            {a.status !== 'Resolved' && (
                              <button
                                type="button"
                                onClick={() => handleUpdateStatus(a.id, 'Resolved')}
                                className="w-7 h-7 rounded-full bg-emerald-100 hover:bg-emerald-200 text-emerald-800 flex items-center justify-center transition-colors cursor-pointer shadow-2xs"
                                title="Quick Resolve"
                              >
                                <Check size={13} strokeWidth={2.5} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* =====================================================================
          DETAILED INCIDENT DOSSIER MODAL (Portaled to document.body)
          ===================================================================== */}
      {selectedAlert && createPortal(
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setSelectedAlert(null)}
        >
          <div 
            className="w-full max-w-[580px] rounded-[32px] overflow-hidden flex flex-col bg-white border border-slate-100 shadow-[0_24px_70px_-12px_rgba(16,38,28,0.3)] animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-7 py-5 border-b border-slate-100 bg-gradient-to-b from-[#f2f8f5]/90 to-white">
              <div className="flex items-center gap-3.5 flex-1 min-w-0 pr-3">
                <div 
                  className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 shadow-md ${
                    selectedAlert.severity === 'Critical' 
                      ? 'bg-red-500 text-white shadow-red-500/25' 
                      : selectedAlert.severity === 'High'
                      ? 'bg-amber-500 text-white shadow-amber-500/25'
                      : 'bg-emerald-600 text-white shadow-emerald-600/25'
                  }`}
                >
                  <ShieldAlert size={22} className="text-white" strokeWidth={2.2} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-extrabold text-[#10261c] text-lg font-display tracking-tight truncate">
                      Incident Dossier #{selectedAlert.id}
                    </h3>
                    <StatusBadge type={selectedAlert.severity} text={selectedAlert.severity} />
                  </div>
                  <p className="text-xs text-[#5d7468] mt-0.5 font-medium">
                    Triggered at {selectedAlert.createdAt} • Real-Time Anomaly Flag
                  </p>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => setSelectedAlert(null)} 
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-800 bg-slate-100/80 hover:bg-slate-200/80 transition-all shrink-0 cursor-pointer hover:rotate-90 duration-200"
                aria-label="Close dialog"
              >
                <X size={16} strokeWidth={2.2} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-7 space-y-4.5 text-xs md:text-sm">
              {/* Center & District Verification Card */}
              <div className="grid grid-cols-2 gap-3 p-4 rounded-2xl bg-slate-50/80 border border-slate-200/80">
                <div>
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wider block">Target FPS Center</span>
                  <span className="font-mono font-bold text-sm text-[#10261c]">{selectedAlert.fps}</span>
                  <span className="text-[11px] text-slate-500 block">{selectedAlert.district} District</span>
                </div>
                <div>
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wider block">Current Status</span>
                  <div className="mt-1">
                    <StatusBadge type={selectedAlert.status} text={selectedAlert.status} />
                  </div>
                  <span className="text-[11px] text-[#14654a] font-semibold block mt-1">Telemetry Live Audited</span>
                </div>
              </div>

              {/* Anomaly Description */}
              <div className="space-y-1">
                <span className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                  Incident Synopsis & Anomaly Flag
                </span>
                <p className="text-xs font-bold text-[#10261c] bg-slate-50 p-3.5 rounded-xl border border-slate-100">
                  {selectedAlert.title}
                </p>
              </div>

              {/* Telemetry Evidence Description */}
              <div className="space-y-1">
                <span className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                  Detailed Diagnostic Evidence
                </span>
                <div className="p-3.5 rounded-2xl bg-[#f2f8f5]/90 border border-[#d3ebd9] text-xs text-slate-700 leading-relaxed font-medium">
                  {selectedAlert.description}
                </div>
              </div>

              {/* 3-Step Remediation Timeline */}
              <div className="space-y-2 pt-1">
                <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider block">
                  Compliance Audit Trail
                </span>
                <div className="flex items-center justify-between text-xs p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="flex items-center gap-2 text-[#14654a] font-bold">
                    <CheckCircle2 size={14} />
                    <span>Neural Flagged</span>
                  </div>
                  <span className="text-slate-300">→</span>
                  <div className="flex items-center gap-2 text-amber-700 font-bold">
                    <Activity size={14} />
                    <span>Evidence Dossier</span>
                  </div>
                  <span className="text-slate-300">→</span>
                  <div className="flex items-center gap-2 text-slate-500 font-semibold">
                    <ShieldCheck size={14} />
                    <span>Field Resolution</span>
                  </div>
                </div>
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => handleUpdateStatus(selectedAlert.id, 'Acknowledged')}
                  className="px-4 py-2.5 rounded-full text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Acknowledge Incident
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      showToast(`Fair Price Shop ${selectedAlert.fps} grain terminal suspended.`);
                      handleUpdateStatus(selectedAlert.id, 'Acknowledged');
                    }}
                    className="px-4 py-2.5 rounded-full text-xs font-bold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200/70 transition-colors cursor-pointer flex items-center gap-1.5"
                  >
                    <Lock size={13} />
                    <span>Freeze Terminal</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleUpdateStatus(selectedAlert.id, 'Resolved')}
                    className="px-5 py-2.5 rounded-full text-xs font-bold text-white shadow-md transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] cursor-pointer flex items-center gap-1.5"
                    style={{
                      background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
                      boxShadow: '0 8px 18px -4px rgba(20, 101, 74, 0.45)'
                    }}
                  >
                    <Check size={14} strokeWidth={2.5} />
                    <span>Mark as Resolved</span>
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
