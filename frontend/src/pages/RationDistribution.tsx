import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { 
  Truck, 
  Scale, 
  ShieldAlert, 
  ArrowUpRight, 
  Search, 
  PlusCircle, 
  X, 
  CheckCircle2, 
  MapPin, 
  Store, 
  FileDown, 
  TrendingUp, 
  Eye, 
  BarChart2,
  PackageCheck
} from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { mockDistricts } from '../data/mockData';
import { District } from '../types';

export const RationDistribution: React.FC = () => {
  const [districts, setDistricts] = useState<District[]>(mockDistricts);
  const [filter, setFilter] = useState<'All' | 'Healthy' | 'Warning' | 'Critical'>('All');
  const [search, setSearch] = useState('');

  // Modals & toast states
  const [isRecordModalOpen, setIsRecordModalOpen] = useState(false);
  const [selectedDistrict, setSelectedDistrict] = useState<District | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Record Distribution Form State
  const [formData, setFormData] = useState({
    district: 'Lucknow',
    fpsCenter: 'FPS-LU-0012',
    commodity: 'Rice',
    quantityKg: 1250,
    vehicleNo: 'UP-32-BN-8421',
    driverName: 'Suresh Kumar'
  });

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleOpenRecordModal = () => {
    setFormData({
      district: 'Lucknow',
      fpsCenter: 'FPS-LU-0012',
      commodity: 'Rice',
      quantityKg: 1250,
      vehicleNo: 'UP-32-BN-8421',
      driverName: 'Suresh Kumar'
    });
    setIsRecordModalOpen(true);
  };

  const handleRecordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const qty = Number(formData.quantityKg) || 0;
    if (qty <= 0) return;

    setDistricts(prev => prev.map(d => {
      if (d.name === formData.district) {
        return {
          ...d,
          distributionsKg: d.distributionsKg + qty,
          transactions: d.transactions + Math.floor(qty / 20)
        };
      }
      return d;
    }));

    setIsRecordModalOpen(false);
    showToast(`Logged distribution of ${qty.toLocaleString()} kg to ${formData.district} (${formData.fpsCenter})`);
  };

  const handleExportCSV = () => {
    const headers = "District,FPS Centers,Distribution Volume (kg),Transactions,Status\n";
    const rows = districts.map(d => `"${d.name}",${d.fpsCenters},${d.distributionsKg},${d.transactions},"${d.status}"`).join("\n");
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ration-distribution-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    showToast("Distribution report exported as CSV");
  };

  // Filtered districts
  const filteredDistricts = districts.filter(d => {
    const matchesFilter = filter === 'All' || d.status === filter;
    const matchesSearch = d.name.toLowerCase().includes(search.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  // Calculate dynamic totals
  const totalAllocatedKg = districts.reduce((acc, d) => acc + d.distributionsKg, 0);
  const totalTransactionsCount = districts.reduce((acc, d) => acc + d.transactions, 0);
  const maxVolume = Math.max(...districts.map(d => d.distributionsKg), 1);

  return (
    <div className="space-y-6 pb-12">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-3 bg-[#0a3d2e] text-white px-5 py-3.5 rounded-2xl shadow-2xl border border-[#7fd8aa]/40 animate-in fade-in slide-in-from-bottom-5">
          <CheckCircle2 size={18} className="text-[#7fd8aa]" />
          <span className="text-xs md:text-sm font-semibold">{toastMessage}</span>
          <button onClick={() => setToastMessage(null)} className="ml-2 text-white/60 hover:text-white">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl md:text-3xl font-extrabold text-[#10261c] tracking-tight font-display">
              Ration Distribution
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase bg-[#2fa56f]/15 text-[#0d6840] border border-[#2fa56f]/30">
              Active Logistics
            </span>
          </div>
          <p className="text-xs md:text-sm text-[#5d7468] mt-1 font-medium">
            Monitor district-level allocation trends, transactional logs, and delivery logistics.
          </p>
        </div>

        {/* Action Buttons: Record Distribution & Export */}
        <div className="flex items-center gap-2.5 self-start sm:self-center">
          <button
            type="button"
            onClick={handleExportCSV}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full border border-slate-200/80 bg-white/80 hover:bg-white text-xs md:text-sm font-bold text-[#10261c] shadow-xs transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          >
            <FileDown size={15} className="text-[#5d7468]" />
            <span>Export CSV</span>
          </button>

          <button
            type="button"
            onClick={handleOpenRecordModal}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full text-white font-bold text-xs md:text-sm shadow-md transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
            style={{
              background: 'linear-gradient(135deg, #062d22, #14654a 52%, #2fa56f)',
              boxShadow: '0 8px 20px -4px rgba(20, 101, 74, 0.45)'
            }}
          >
            <PlusCircle size={16} />
            <span>Record Distribution</span>
          </button>
        </div>
      </div>

      {/* 4 Redesigned Glass KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Ration Allocated */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Ration Allocated</span>
            <div className="w-8 h-8 rounded-full bg-[#14654a]/12 flex items-center justify-center text-[#14654a]">
              <Truck size={17} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              {totalAllocatedKg.toLocaleString(undefined, { maximumFractionDigits: 1 })} kg
            </span>
            <span className="text-[11px] font-bold text-[#0d6840] flex items-center gap-0.5">
              <TrendingUp size={12} />
              +9.7% 7d
            </span>
          </div>
        </div>

        {/* Card 2: Total Transactions */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Total Transactions</span>
            <div className="w-8 h-8 rounded-full bg-[#2fa56f]/15 flex items-center justify-center text-[#14654a]">
              <ArrowUpRight size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#14654a] font-display">
              {totalTransactionsCount.toLocaleString()} records
            </span>
            <span className="text-[11px] font-bold text-[#14654a] flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2fa56f] animate-pulse"></span>
              Live sync
            </span>
          </div>
        </div>

        {/* Card 3: Average Quota Fill */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Average Quota Fill</span>
            <div className="w-8 h-8 rounded-full bg-[#5b3df5]/12 flex items-center justify-center text-[#5b3df5]">
              <Scale size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              94.8%
            </span>
            <span className="text-[11px] font-bold text-slate-500">
              Target: 95%
            </span>
          </div>
        </div>

        {/* Card 4: Critical Anomalies */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Critical Anomalies</span>
            <div className="w-8 h-8 rounded-full bg-[#ef5b4a]/15 flex items-center justify-center text-[#ef5b4a]">
              <ShieldAlert size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#ef5b4a] font-display">
              3 Cases
            </span>
            <span className="text-[11px] font-bold text-[#ef5b4a] bg-[#ef5b4a]/10 px-2 py-0.5 rounded-full">
              East Delhi Flagged
            </span>
          </div>
        </div>
      </div>

      {/* Visual Volume Comparison Card */}
      <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[28px] p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart2 size={18} className="text-[#14654a]" />
            <h3 className="font-extrabold text-[#10261c] text-sm md:text-base font-display">
              District Allocation Volume Breakdown
            </h3>
          </div>
          <span className="text-xs text-[#5d7468] font-medium hidden sm:inline">
            Relative quota distribution across top districts
          </span>
        </div>

        <div className="space-y-3 pt-1">
          {districts.map(d => {
            const percent = (d.distributionsKg / maxVolume) * 100;
            const barColor = d.status === 'Critical' 
              ? 'bg-gradient-to-r from-red-500 to-[#ef5b4a]' 
              : d.status === 'Warning'
              ? 'bg-gradient-to-r from-amber-500 to-amber-400'
              : 'bg-gradient-to-r from-[#14654a] to-[#2fa56f]';

            return (
              <div key={d.name} className="space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="text-[#10261c] flex items-center gap-1.5">
                    <span className="font-bold">{d.name}</span>
                    <span className="text-[11px] text-[#7a8b84]">({d.fpsCenters} FPS Centers)</span>
                  </span>
                  <span className="font-mono font-bold text-[#10261c]">
                    {d.distributionsKg.toLocaleString()} kg
                  </span>
                </div>
                <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden flex">
                  <div 
                    className={`h-full rounded-full transition-all duration-700 ${barColor}`}
                    style={{ width: `${percent}%` }}
                  ></div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Status Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
          {(['All', 'Healthy', 'Warning', 'Critical'] as const).map((s) => {
            const count = s === 'All'
              ? districts.length
              : districts.filter(d => d.status === s).length;
            const isActive = filter === s;

            return (
              <button
                key={s}
                type="button"
                onClick={() => setFilter(s)}
                className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold transition-all duration-200 whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'bg-[#14654a] text-white shadow-sm'
                    : 'bg-white/80 border border-slate-200/80 text-[#5d7468] hover:bg-slate-50 hover:text-[#10261c]'
                }`}
              >
                <span>{s}</span>
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                  isActive ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500'
                }`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Search */}
        <div className="relative w-full md:w-72">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#7a8b84]" />
          <input
            type="text"
            placeholder="Search district name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-9 pl-9 pr-8 border border-slate-200/80 rounded-full text-xs font-medium focus:outline-none focus:border-[#14654a] focus:ring-1 focus:ring-[#14654a] bg-white/90 text-[#10261c] transition-all"
          />
          {search && (
            <button 
              onClick={() => setSearch('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Main District Table */}
      <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[28px] p-5 shadow-sm overflow-hidden space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-extrabold text-[#10261c] text-sm md:text-base font-display">
            District-wise Allocation & Activity
          </h3>
          <span className="text-xs text-[#7a8b84]">
            Showing {filteredDistricts.length} of {districts.length} districts
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs md:text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-[#7a8b84] font-bold tracking-wider text-[10.5px] uppercase">
                <th className="py-3 px-4">District</th>
                <th className="py-3 px-4">FPS Centers</th>
                <th className="py-3 px-4">Distributions Volume</th>
                <th className="py-3 px-4">Transactions</th>
                <th className="py-3 px-4">Avg / Center</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filteredDistricts.map((d) => {
                const avgPerFps = Math.round(d.distributionsKg / d.fpsCenters);

                return (
                  <tr 
                    key={d.name} 
                    onClick={() => setSelectedDistrict(d)}
                    className="hover:bg-[#ebf5f0]/60 transition-colors duration-150 cursor-pointer group"
                  >
                    {/* District Name with Icon */}
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-full bg-[#14654a]/10 text-[#14654a] flex items-center justify-center shrink-0">
                          <MapPin size={14} />
                        </div>
                        <span className="font-extrabold text-[#10261c] group-hover:text-[#14654a] transition-colors">
                          {d.name}
                        </span>
                      </div>
                    </td>

                    {/* FPS Centers */}
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-1.5 font-semibold text-[#5d7468]">
                        <Store size={13} className="text-[#7a8b84]" />
                        <span>{d.fpsCenters}</span>
                      </div>
                    </td>

                    {/* Distributions Volume */}
                    <td className="py-3.5 px-4">
                      <span className="font-bold text-[#10261c] font-display text-sm">
                        {d.distributionsKg.toLocaleString()} kg
                      </span>
                    </td>

                    {/* Total Transactions */}
                    <td className="py-3.5 px-4 font-mono font-semibold text-[#5d7468]">
                      {d.transactions.toLocaleString()}
                    </td>

                    {/* Avg / Center */}
                    <td className="py-3.5 px-4 text-slate-600 font-medium">
                      {avgPerFps.toLocaleString()} kg/FPS
                    </td>

                    {/* Status */}
                    <td className="py-3.5 px-4">
                      <StatusBadge type={d.status} text={d.status} />
                    </td>

                    {/* Action Button */}
                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedDistrict(d);
                        }}
                        className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold text-[#14654a] hover:bg-[#14654a]/10 transition-colors"
                      >
                        <Eye size={13} />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                );
              })}

              {filteredDistricts.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-xs text-[#7a8b84]">
                    No districts matching filter query.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* =====================================================================
          RECORD NEW DISTRIBUTION BATCH MODAL
          ===================================================================== */}
      {isRecordModalOpen && createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-200" onClick={() => setIsRecordModalOpen(false)}>
          <div 
            className="bg-white border border-white/80 rounded-[28px] shadow-2xl w-full max-w-lg overflow-hidden flex flex-col animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4.5 border-b border-slate-100 bg-[#e7f0eb]/50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[#14654a]/15 text-[#14654a] flex items-center justify-center shrink-0">
                  <PackageCheck size={20} />
                </div>
                <div>
                  <h3 className="font-extrabold text-[#10261c] text-base leading-tight font-display">
                    Record Distribution Dispatch
                  </h3>
                  <p className="text-xs text-[#5d7468] mt-0.5">
                    Log new grain consignment dispatched to Fair Price Shops
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setIsRecordModalOpen(false)} 
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleRecordSubmit} className="p-6 space-y-4 text-xs md:text-sm">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {/* District */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Destination District *
                  </label>
                  <select
                    value={formData.district}
                    onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-[#14654a] text-[#10261c] bg-white"
                  >
                    {districts.map(d => (
                      <option key={d.name} value={d.name}>{d.name}</option>
                    ))}
                  </select>
                </div>

                {/* Destination FPS Center */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Destination FPS Center *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. FPS-LU-0012"
                    value={formData.fpsCenter}
                    onChange={(e) => setFormData({ ...formData, fpsCenter: e.target.value })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-mono font-bold text-[#10261c]"
                  />
                </div>

                {/* Commodity Type */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Commodity *
                  </label>
                  <select
                    value={formData.commodity}
                    onChange={(e) => setFormData({ ...formData, commodity: e.target.value })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-[#14654a] text-[#10261c] bg-white"
                  >
                    <option value="Rice">Rice (NFSA Fortified)</option>
                    <option value="Wheat">Wheat (Standard)</option>
                    <option value="Coarse Grain">Coarse Grains / Millets</option>
                  </select>
                </div>

                {/* Quantity Dispatched (kg) */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Dispatched Quantity (kg) *
                  </label>
                  <input
                    type="number"
                    min="50"
                    step="25"
                    required
                    value={formData.quantityKg}
                    onChange={(e) => setFormData({ ...formData, quantityKg: Number(e.target.value) })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-bold text-[#10261c]"
                  />
                </div>

                {/* Vehicle Transport No */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Vehicle Transport No.
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. DL-01-EA-4821"
                    value={formData.vehicleNo}
                    onChange={(e) => setFormData({ ...formData, vehicleNo: e.target.value })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-semibold text-[#10261c]"
                  />
                </div>

                {/* Dispatch Officer */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Authorized Driver / Agent
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Suresh Kumar"
                    value={formData.driverName}
                    onChange={(e) => setFormData({ ...formData, driverName: e.target.value })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-semibold text-[#10261c]"
                  />
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2.5 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsRecordModalOpen(false)}
                  className="px-4 py-2 rounded-full border border-slate-200 text-xs font-bold text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-full text-white text-xs font-bold shadow-md transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
                  style={{
                    background: 'linear-gradient(135deg, #062d22, #14654a 52%, #2fa56f)',
                    boxShadow: '0 8px 18px -4px rgba(20, 101, 74, 0.45)'
                  }}
                >
                  Confirm Dispatch
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}

      {/* =====================================================================
          DISTRICT LOGISTICS DETAIL MODAL
          ===================================================================== */}
      {selectedDistrict && createPortal(
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setSelectedDistrict(null)}
        >
          <div 
            className="bg-white border border-white/80 rounded-[28px] shadow-2xl w-full max-w-lg overflow-hidden flex flex-col animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4.5 border-b border-slate-100 bg-[#e7f0eb]/50">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-full bg-[#14654a]/15 text-[#14654a] flex items-center justify-center shrink-0">
                  <MapPin size={22} />
                </div>
                <div>
                  <h3 className="font-extrabold text-[#10261c] text-lg leading-tight font-display">
                    {selectedDistrict.name} District Logistics
                  </h3>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs font-bold text-[#5d7468]">
                      {selectedDistrict.fpsCenters} Registered FPS Centers
                    </span>
                    <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                    <StatusBadge type={selectedDistrict.status} text={selectedDistrict.status} />
                  </div>
                </div>
              </div>
              <button 
                onClick={() => setSelectedDistrict(null)} 
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Content */}
            <div className="p-6 space-y-4 text-xs md:text-sm">
              <div className="grid grid-cols-2 gap-3.5 bg-slate-50 p-4 rounded-2xl border border-slate-100">
                <div>
                  <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide block">
                    Total Volume Dispatched
                  </span>
                  <strong className="text-base text-[#10261c] font-display mt-0.5 block">
                    {selectedDistrict.distributionsKg.toLocaleString()} kg
                  </strong>
                </div>
                <div>
                  <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide block">
                    Verified Transactions
                  </span>
                  <strong className="text-base text-[#10261c] font-display mt-0.5 block">
                    {selectedDistrict.transactions.toLocaleString()} tx
                  </strong>
                </div>
                <div>
                  <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide block">
                    Avg Per Fair Price Shop
                  </span>
                  <strong className="text-base text-[#14654a] font-display mt-0.5 block">
                    {Math.round(selectedDistrict.distributionsKg / selectedDistrict.fpsCenters).toLocaleString()} kg/FPS
                  </strong>
                </div>
                <div>
                  <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide block">
                    Quota Allocation Status
                  </span>
                  <strong className={`text-base font-display mt-0.5 block ${
                    selectedDistrict.status === 'Critical' ? 'text-red-600' : 'text-green-700'
                  }`}>
                    {selectedDistrict.status === 'Critical' ? 'Anomaly Detected' : 'Optimal Flow'}
                  </strong>
                </div>
              </div>

              {/* Status Notice */}
              {selectedDistrict.status === 'Critical' && (
                <div className="bg-red-50 border border-red-200 rounded-2xl p-4 flex items-start gap-3 text-red-800">
                  <ShieldAlert size={18} className="text-red-600 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-bold text-xs uppercase tracking-wide">High Temporal Anomaly Rate</h4>
                    <p className="text-xs text-red-700 mt-0.5">
                      AI anomaly detection detected 3 temporal distribution mismatches at FPS centers in this district. Audit team has been assigned.
                    </p>
                  </div>
                </div>
              )}

              {/* Close & Action Buttons */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedDistrict(null);
                    showToast(`Dispatched emergency buffer inspection for ${selectedDistrict.name}`);
                  }}
                  className="px-4 py-2 rounded-full border border-slate-200 text-xs font-bold text-[#14654a] hover:bg-emerald-50 transition-colors"
                >
                  Request Field Audit
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedDistrict(null)}
                  className="px-5 py-2 rounded-full text-white text-xs font-bold shadow-xs bg-[#14654a] hover:bg-[#0b5c39] transition-colors"
                >
                  Close Details
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};
