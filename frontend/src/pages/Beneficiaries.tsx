import React, { useState } from 'react';
import { Search, UserPlus, ShieldCheck, HelpCircle } from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { mockBeneficiaries } from '../data/mockData';

export const Beneficiaries: React.FC = () => {
  const [search, setSearch] = useState('');
  const [riskFilter, setRiskFilter] = useState<'All' | 'Low' | 'Medium' | 'High' | 'Critical'>('All');

  const filtered = mockBeneficiaries.filter(b => {
    const matchesRisk = riskFilter === 'All' || b.risk === riskFilter;
    const matchesSearch = b.name.toLowerCase().includes(search.toLowerCase()) ||
                          b.id.toLowerCase().includes(search.toLowerCase()) ||
                          b.fps.toLowerCase().includes(search.toLowerCase()) ||
                          b.district.toLowerCase().includes(search.toLowerCase());
    return matchesRisk && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">Beneficiaries</h1>
          <p className="text-xs md:text-sm text-slate-500 mt-1">
            Manage beneficiary registries, verification statuses, and spatial risk mappings.
          </p>
        </div>
        <button
          onClick={() => alert('New registration request.')}
          className="self-start sm:self-center flex items-center justify-center gap-1.5 px-3-4 py-2 bg-[#0284C7] hover:bg-[#0369A1] text-white rounded text-xs font-bold shadow-xs transition-colors"
        >
          <UserPlus size={14} />
          <span>Add Beneficiary</span>
        </button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Total Beneficiaries</span>
            <span className="text-lg font-bold text-slate-800">24,582</span>
          </div>
          <div className="w-8 h-8 rounded bg-sky-50 text-[#0284C7] flex items-center justify-center">
            <span className="text-xs font-bold">24k</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Active (7 Days)</span>
            <span className="text-lg font-bold text-green-600">23,410</span>
          </div>
          <ShieldCheck size={20} className="text-green-500" />
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Flagged / High Risk</span>
            <span className="text-lg font-bold text-red-600">148</span>
          </div>
          <div className="w-8 h-8 rounded bg-red-50 text-red-600 flex items-center justify-center">
            <span className="text-xs font-bold">148</span>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Pending Verification</span>
            <span className="text-lg font-bold text-orange-500">290</span>
          </div>
          <HelpCircle size={20} className="text-orange-500" />
        </div>
      </div>

      {/* Toolbar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Risk filters */}
        <div className="flex gap-1.5 border-b border-slate-100 md:border-b-0 pb-2 md:pb-0 overflow-x-auto">
          {(['All', 'Low', 'Medium', 'High', 'Critical'] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRiskFilter(r)}
              className={`px-3 py-1.5 rounded text-xs font-semibold whitespace-nowrap transition-colors ${
                riskFilter === r 
                  ? 'bg-[#E0F2FE] text-[#0369A1]' 
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
              }`}
            >
              {r} Risk
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full md:w-64">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search beneficiaries..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-8 pl-9 pr-4 border border-slate-200 rounded text-xs focus:outline-none focus:border-sky-500 text-slate-700"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-lg p-5">
        <div className="overflow-x-auto border border-slate-100 rounded-lg">
          <table className="w-full text-left border-collapse text-xs md:text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold tracking-wider text-[10px] uppercase">
                <th className="py-3 px-4 font-bold">Beneficiary ID</th>
                <th className="py-3 px-4 font-bold">Name</th>
                <th className="py-3 px-4 font-bold">District</th>
                <th className="py-3 px-4 font-bold">FPS Center</th>
                <th className="py-3 px-4 font-bold">Family Members</th>
                <th className="py-3 px-4 font-bold">Risk Level</th>
                <th className="py-3 px-4 font-bold">Status</th>
                <th className="py-3 px-4 font-bold">Last Transacted</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((b) => (
                <tr key={b.id} className="border-b border-slate-50 hover:bg-slate-50/70 transition-colors text-slate-700">
                  <td className="py-3 px-4 font-mono font-bold text-slate-500">{b.id}</td>
                  <td className="py-3 px-4 font-semibold text-slate-800">{b.name}</td>
                  <td className="py-3 px-4 font-medium">{b.district}</td>
                  <td className="py-3 px-4 font-mono text-xs">{b.fps}</td>
                  <td className="py-3 px-4 tabular-nums">{b.familyMembers}</td>
                  <td className="py-3 px-4">
                    <StatusBadge type={b.risk} text={b.risk} />
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge type={b.status} text={b.status} />
                  </td>
                  <td className="py-3 px-4 text-xs text-slate-400">{b.lastDistribution}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-xs text-slate-400">No beneficiaries matching filter found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
