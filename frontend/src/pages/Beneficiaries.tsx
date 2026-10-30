import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { 
  Search, 
  UserPlus, 
  ShieldCheck, 
  AlertTriangle, 
  Clock, 
  Users, 
  X, 
  CheckCircle2, 
  Eye, 
  Trash2,
  FileText,
  MapPin,
  Store
} from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { mockBeneficiaries } from '../data/mockData';
import { Beneficiary } from '../types';

export const Beneficiaries: React.FC = () => {
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>(mockBeneficiaries);
  const [search, setSearch] = useState('');
  const [riskFilter, setRiskFilter] = useState<'All' | 'Low' | 'Medium' | 'High' | 'Critical'>('All');
  
  // Modals state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [selectedBeneficiary, setSelectedBeneficiary] = useState<Beneficiary | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Add Beneficiary Form State
  const [formData, setFormData] = useState({
    name: '',
    id: `BEN-${Math.floor(10000 + Math.random() * 90000)}`,
    district: 'Delhi',
    fps: 'FPS-DL-0021',
    familyMembers: 4,
    schemeType: 'PHH',
    risk: 'Low' as 'Low' | 'Medium' | 'High' | 'Critical',
    status: 'Verified' as 'Verified' | 'Pending' | 'Flagged'
  });

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleOpenAddModal = () => {
    setFormData({
      name: '',
      id: `BEN-${Math.floor(10000 + Math.random() * 90000)}`,
      district: 'Delhi',
      fps: 'FPS-DL-0021',
      familyMembers: 4,
      schemeType: 'PHH',
      risk: 'Low',
      status: 'Verified'
    });
    setIsAddModalOpen(true);
  };

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;

    const newBen: Beneficiary = {
      id: formData.id.trim() || `BEN-${Math.floor(10000 + Math.random() * 90000)}`,
      name: formData.name.trim(),
      district: formData.district,
      fps: formData.fps.trim() || 'FPS-DL-0001',
      familyMembers: Number(formData.familyMembers) || 1,
      schemeType: formData.schemeType,
      risk: formData.risk,
      status: formData.status,
      lastDistribution: new Date().toISOString().split('T')[0]
    };

    setBeneficiaries(prev => [newBen, ...prev]);
    setIsAddModalOpen(false);
    showToast(`Beneficiary ${newBen.name} (${newBen.id}) successfully registered!`);
  };

  const handleToggleStatus = (id: string, newStatus: 'Verified' | 'Flagged' | 'Pending') => {
    setBeneficiaries(prev => prev.map(b => b.id === id ? { ...b, status: newStatus } : b));
    if (selectedBeneficiary && selectedBeneficiary.id === id) {
      setSelectedBeneficiary(prev => prev ? { ...prev, status: newStatus } : null);
    }
    showToast(`Status updated to ${newStatus}`);
  };

  const handleDeleteBeneficiary = (id: string) => {
    setBeneficiaries(prev => prev.filter(b => b.id !== id));
    if (selectedBeneficiary && selectedBeneficiary.id === id) {
      setSelectedBeneficiary(null);
    }
    showToast(`Beneficiary record removed`);
  };

  // Filter logic
  const filtered = beneficiaries.filter(b => {
    const matchesRisk = riskFilter === 'All' || b.risk === riskFilter;
    const q = search.toLowerCase();
    const matchesSearch = 
      b.name.toLowerCase().includes(q) ||
      b.id.toLowerCase().includes(q) ||
      b.fps.toLowerCase().includes(q) ||
      b.district.toLowerCase().includes(q) ||
      b.schemeType.toLowerCase().includes(q);
    return matchesRisk && matchesSearch;
  });

  // Dynamic counts
  const totalBeneficiariesCount = 24582 + (beneficiaries.length - mockBeneficiaries.length);
  const flaggedCount = 148 + beneficiaries.filter(b => b.risk === 'High' || b.risk === 'Critical').length - mockBeneficiaries.filter(b => b.risk === 'High' || b.risk === 'Critical').length;
  const pendingCount = 290 + beneficiaries.filter(b => b.status === 'Pending').length - mockBeneficiaries.filter(b => b.status === 'Pending').length;

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

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl md:text-3xl font-extrabold text-[#10261c] tracking-tight font-display">
              Beneficiaries
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase bg-[#2fa56f]/15 text-[#0d6840] border border-[#2fa56f]/30">
              Live Registry
            </span>
          </div>
          <p className="text-xs md:text-sm text-[#5d7468] mt-1 font-medium">
            Manage citizen entitlements, biometrics, verification states, and anomaly flags.
          </p>
        </div>

        {/* Action Button: Emerald Pill Add Beneficiary */}
        <button
          onClick={handleOpenAddModal}
          type="button"
          className="self-start sm:self-center inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full text-white font-bold text-xs md:text-sm shadow-md transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          style={{
            background: 'linear-gradient(135deg, #062d22, #14654a 52%, #2fa56f)',
            boxShadow: '0 8px 20px -4px rgba(20, 101, 74, 0.45)'
          }}
        >
          <UserPlus size={16} />
          <span>Add Beneficiary</span>
        </button>
      </div>

      {/* 4 KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Beneficiaries */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Total Beneficiaries</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#e1f0e7] text-[#14654a]">
              24.5k
            </span>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              {totalBeneficiariesCount.toLocaleString()}
            </span>
            <span className="text-[11px] font-bold text-[#14654a] flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2fa56f] animate-pulse"></span>
              95.2% active
            </span>
          </div>
        </div>

        {/* Card 2: Active (7 Days) */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Active (7 Days)</span>
            <div className="w-8 h-8 rounded-full bg-[#2fa56f]/15 flex items-center justify-center text-[#14654a]">
              <ShieldCheck size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#14654a] font-display">
              23,410
            </span>
            <span className="text-[11px] font-bold text-[#0d6840]">
              ↑ 3.2% vs last week
            </span>
          </div>
        </div>

        {/* Card 3: Flagged / High Risk */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Flagged / High Risk</span>
            <div className="w-8 h-8 rounded-full bg-[#ef5b4a]/15 flex items-center justify-center text-[#ef5b4a]">
              <AlertTriangle size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#ef5b4a] font-display">
              {flaggedCount}
            </span>
            <span className="text-[11px] font-bold text-[#ef5b4a] bg-[#ef5b4a]/10 px-2 py-0.5 rounded-full">
              Critical priority
            </span>
          </div>
        </div>

        {/* Card 4: Pending Verification */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Pending Verification</span>
            <div className="w-8 h-8 rounded-full bg-amber-500/15 flex items-center justify-center text-amber-600">
              <Clock size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-amber-600 font-display">
              {pendingCount}
            </span>
            <span className="text-[11px] font-bold text-amber-700">
              Review required
            </span>
          </div>
        </div>
      </div>

      {/* Toolbar: Filter Pills + Search */}
      <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Risk Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
          {(['All', 'Low', 'Medium', 'High', 'Critical'] as const).map((r) => {
            const count = r === 'All' 
              ? beneficiaries.length 
              : beneficiaries.filter(b => b.risk === r).length;
            const isActive = riskFilter === r;

            return (
              <button
                key={r}
                type="button"
                onClick={() => setRiskFilter(r)}
                className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold transition-all duration-200 whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'bg-[#14654a] text-white shadow-sm'
                    : 'bg-white/80 border border-slate-200/80 text-[#5d7468] hover:bg-slate-50 hover:text-[#10261c]'
                }`}
              >
                <span>{r} Risk</span>
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                  isActive ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500'
                }`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Search Field */}
        <div className="relative w-full md:w-72">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#7a8b84]" />
          <input
            type="text"
            placeholder="Search name, ID, district..."
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

      {/* Main Beneficiaries Table */}
      <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[28px] p-5 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs md:text-sm">
            <thead>
              <tr className="border-b border-slate-100/90 text-[#7a8b84] font-bold tracking-wider text-[10.5px] uppercase">
                <th className="py-3 px-4">Beneficiary</th>
                <th className="py-3 px-4">District</th>
                <th className="py-3 px-4">FPS Center</th>
                <th className="py-3 px-4">Scheme</th>
                <th className="py-3 px-4">Members</th>
                <th className="py-3 px-4">Risk Level</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Last Transacted</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {filtered.map((b) => (
                <tr 
                  key={b.id} 
                  onClick={() => setSelectedBeneficiary(b)}
                  className="hover:bg-[#ebf5f0]/60 transition-colors duration-150 cursor-pointer group"
                >
                  {/* Name + ID */}
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#1b4a35] to-[#348060] text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-xs">
                        {b.name.charAt(0)}
                      </div>
                      <div>
                        <span className="font-bold text-[#10261c] block group-hover:text-[#14654a] transition-colors">
                          {b.name}
                        </span>
                        <span className="font-mono text-[11px] text-[#7a8b84]">
                          {b.id}
                        </span>
                      </div>
                    </div>
                  </td>

                  {/* District */}
                  <td className="py-3 px-4 font-semibold text-[#10261c]">
                    {b.district}
                  </td>

                  {/* FPS Center */}
                  <td className="py-3 px-4 font-mono text-[11.5px] text-[#5d7468]">
                    {b.fps}
                  </td>

                  {/* Scheme Type */}
                  <td className="py-3 px-4">
                    <span className="px-2 py-0.5 rounded-full text-[10.5px] font-bold bg-slate-100 text-slate-700 border border-slate-200/60">
                      {b.schemeType || 'PHH'}
                    </span>
                  </td>

                  {/* Family Members */}
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-1.5 font-bold text-[#10261c]">
                      <Users size={13} className="text-[#7a8b84]" />
                      <span>{b.familyMembers}</span>
                    </div>
                  </td>

                  {/* Risk Level */}
                  <td className="py-3 px-4">
                    <StatusBadge type={b.risk} text={b.risk} />
                  </td>

                  {/* Status */}
                  <td className="py-3 px-4">
                    <StatusBadge type={b.status} text={b.status} />
                  </td>

                  {/* Last Transacted */}
                  <td className="py-3 px-4 text-xs text-[#7a8b84]">
                    {b.lastDistribution}
                  </td>

                  {/* Action Button */}
                  <td className="py-3 px-4 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedBeneficiary(b);
                      }}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold text-[#14654a] hover:bg-[#14654a]/10 transition-colors"
                    >
                      <Eye size={13} />
                      <span>View</span>
                    </button>
                  </td>
                </tr>
              ))}

              {filtered.length === 0 && (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-xs text-[#7a8b84]">
                    No beneficiaries matching current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* =====================================================================
          ADD BENEFICIARY MODAL DIALOG
          ===================================================================== */}
      {isAddModalOpen && createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-200" onClick={() => setIsAddModalOpen(false)}>
          <div 
            className="bg-white border border-white/80 rounded-[28px] shadow-2xl w-full max-w-lg overflow-hidden flex flex-col animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4.5 border-b border-slate-100 bg-[#e7f0eb]/50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-[#14654a]/15 text-[#14654a] flex items-center justify-center shrink-0">
                  <UserPlus size={20} />
                </div>
                <div>
                  <h3 className="font-extrabold text-[#10261c] text-base leading-tight font-display">
                    Register New Beneficiary
                  </h3>
                  <p className="text-xs text-[#5d7468] mt-0.5">
                    Add beneficiary citizen record to the PDS distribution registry
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setIsAddModalOpen(false)} 
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleAddSubmit} className="p-6 space-y-4 text-xs md:text-sm">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {/* Full Name */}
                <div className="sm:col-span-2 space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Beneficiary Full Name *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Meera Devi"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-[#14654a] focus:ring-1 focus:ring-[#14654a] text-[#10261c]"
                  />
                </div>

                {/* Beneficiary ID */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Beneficiary ID
                  </label>
                  <input
                    type="text"
                    value={formData.id}
                    onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-700 bg-slate-50/70"
                  />
                </div>

                {/* District */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    District
                  </label>
                  <select
                    value={formData.district}
                    onChange={(e) => setFormData({ ...formData, district: e.target.value })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-[#14654a] text-[#10261c] bg-white"
                  >
                    <option value="Delhi">Delhi</option>
                    <option value="East Delhi">East Delhi</option>
                    <option value="Lucknow">Lucknow</option>
                    <option value="Gwalior">Gwalior</option>
                    <option value="Aurangabad">Aurangabad</option>
                  </select>
                </div>

                {/* Assigned FPS Center */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Assigned FPS Center
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. FPS-DL-0042"
                    value={formData.fps}
                    onChange={(e) => setFormData({ ...formData, fps: e.target.value })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-[#14654a] text-[#10261c]"
                  />
                </div>

                {/* Family Members */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Family Members
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="15"
                    value={formData.familyMembers}
                    onChange={(e) => setFormData({ ...formData, familyMembers: Number(e.target.value) })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-[#14654a] text-[#10261c]"
                  />
                </div>

                {/* Scheme Type */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Scheme Type
                  </label>
                  <select
                    value={formData.schemeType}
                    onChange={(e) => setFormData({ ...formData, schemeType: e.target.value })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-[#14654a] text-[#10261c] bg-white"
                  >
                    <option value="PHH">PHH (Priority Household)</option>
                    <option value="AAY">AAY (Antyodaya Anna Yojana)</option>
                    <option value="NPHH">NPHH (Non-Priority)</option>
                  </select>
                </div>

                {/* Risk Level */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide">
                    Initial Risk Level
                  </label>
                  <select
                    value={formData.risk}
                    onChange={(e) => setFormData({ ...formData, risk: e.target.value as any })}
                    className="w-full px-3.5 py-2 border border-slate-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-[#14654a] text-[#10261c] bg-white"
                  >
                    <option value="Low">Low Risk</option>
                    <option value="Medium">Medium Risk</option>
                    <option value="High">High Risk</option>
                    <option value="Critical">Critical Risk</option>
                  </select>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2.5 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
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
                  Register Beneficiary
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}

      {/* =====================================================================
          BENEFICIARY DETAILS DRAWER / MODAL
          ===================================================================== */}
      {selectedBeneficiary && createPortal(
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setSelectedBeneficiary(null)}
        >
          <div 
            className="bg-white border border-white/80 rounded-[28px] shadow-2xl w-full max-w-lg overflow-hidden flex flex-col animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4.5 border-b border-slate-100 bg-[#e7f0eb]/50">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-full bg-gradient-to-br from-[#1b4a35] to-[#348060] text-white font-extrabold text-sm flex items-center justify-center shadow-sm">
                  {selectedBeneficiary.name.charAt(0)}
                </div>
                <div>
                  <h3 className="font-extrabold text-[#10261c] text-lg leading-tight font-display">
                    {selectedBeneficiary.name}
                  </h3>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="font-mono text-xs text-[#5d7468]">
                      {selectedBeneficiary.id}
                    </span>
                    <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                    <span className="text-xs font-bold text-[#14654a]">
                      {selectedBeneficiary.schemeType} Cardholder
                    </span>
                  </div>
                </div>
              </div>
              <button 
                onClick={() => setSelectedBeneficiary(null)} 
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Profile Content */}
            <div className="p-6 space-y-4 text-xs md:text-sm">
              {/* Badges row */}
              <div className="flex items-center justify-between bg-slate-50 p-3.5 rounded-2xl border border-slate-100">
                <div className="space-y-0.5">
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wide block">Verification State</span>
                  <StatusBadge type={selectedBeneficiary.status} text={selectedBeneficiary.status} />
                </div>
                <div className="space-y-0.5 text-right">
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wide block">Risk Classification</span>
                  <StatusBadge type={selectedBeneficiary.risk} text={`${selectedBeneficiary.risk} Risk`} />
                </div>
              </div>

              {/* Grid Details */}
              <div className="grid grid-cols-2 gap-3.5 bg-white p-4 rounded-2xl border border-slate-100 shadow-xs">
                <div>
                  <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide flex items-center gap-1">
                    <MapPin size={12} /> District
                  </span>
                  <strong className="text-sm text-[#10261c] mt-0.5 block">{selectedBeneficiary.district}</strong>
                </div>
                <div>
                  <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide flex items-center gap-1">
                    <Store size={12} /> Assigned FPS Center
                  </span>
                  <strong className="text-sm font-mono text-[#10261c] mt-0.5 block">{selectedBeneficiary.fps}</strong>
                </div>
                <div>
                  <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide flex items-center gap-1">
                    <Users size={12} /> Family Members
                  </span>
                  <strong className="text-sm text-[#10261c] mt-0.5 block">{selectedBeneficiary.familyMembers} Persons</strong>
                </div>
                <div>
                  <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wide flex items-center gap-1">
                    <FileText size={12} /> Monthly Quota
                  </span>
                  <strong className="text-sm text-[#14654a] mt-0.5 block">
                    {selectedBeneficiary.familyMembers * 5} kg Grain
                  </strong>
                </div>
              </div>

              {/* Quota Breakdown */}
              <div className="bg-[#e1f0e7]/40 border border-[#2fa56f]/20 rounded-2xl p-4">
                <div className="flex items-center justify-between text-xs font-bold text-[#14654a] mb-2">
                  <span>Entitlement Breakdown (NFSA Standard)</span>
                  <span>{selectedBeneficiary.familyMembers * 5} kg / month</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-white rounded-lg p-2 border border-[#2fa56f]/20 text-center">
                    <span className="text-[10px] text-slate-500 font-bold block">Rice (3kg/member)</span>
                    <span className="text-xs font-extrabold text-[#10261c]">{selectedBeneficiary.familyMembers * 3} kg</span>
                  </div>
                  <div className="flex-1 bg-white rounded-lg p-2 border border-[#2fa56f]/20 text-center">
                    <span className="text-[10px] text-slate-500 font-bold block">Wheat (2kg/member)</span>
                    <span className="text-xs font-extrabold text-[#10261c]">{selectedBeneficiary.familyMembers * 2} kg</span>
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => handleDeleteBeneficiary(selectedBeneficiary.id)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold text-red-600 hover:bg-red-50 transition-colors"
                >
                  <Trash2 size={13} />
                  <span>Remove Record</span>
                </button>

                <div className="flex items-center gap-2">
                  {selectedBeneficiary.status !== 'Verified' && (
                    <button
                      type="button"
                      onClick={() => handleToggleStatus(selectedBeneficiary.id, 'Verified')}
                      className="px-3.5 py-1.5 rounded-full text-xs font-bold text-white bg-[#14654a] hover:bg-[#0b5c39] transition-colors"
                    >
                      Verify Beneficiary
                    </button>
                  )}
                  {selectedBeneficiary.status !== 'Flagged' && (
                    <button
                      type="button"
                      onClick={() => handleToggleStatus(selectedBeneficiary.id, 'Flagged')}
                      className="px-3.5 py-1.5 rounded-full text-xs font-bold text-red-700 bg-red-100 hover:bg-red-200 transition-colors"
                    >
                      Flag for Audit
                    </button>
                  )}
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
