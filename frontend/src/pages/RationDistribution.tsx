import React, { useState } from 'react';
import { Truck, Scale, ShieldAlert, ArrowUpRight, Search } from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { mockDistricts } from '../data/mockData';

export const RationDistribution: React.FC = () => {
  const [filter, setFilter] = useState<'All' | 'Healthy' | 'Warning' | 'Critical'>('All');
  const [search, setSearch] = useState('');

  const filteredDistricts = mockDistricts.filter(d => {
    const matchesFilter = filter === 'All' || d.status === filter;
    const matchesSearch = d.name.toLowerCase().includes(search.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">Ration Distribution</h1>
        <p className="text-xs md:text-sm text-slate-500 mt-1">
          Monitor district-level allocation trends, transactional logs, and delivery logistics.
        </p>
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Ration Allocated</span>
            <span className="text-lg font-bold text-slate-800">43,450.5 kg</span>
          </div>
          <Truck size={20} className="text-[#0284C7]" />
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Total Transactions</span>
            <span className="text-lg font-bold text-slate-800">4,520 records</span>
          </div>
          <ArrowUpRight size={20} className="text-green-500" />
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Average Quota Fill</span>
            <span className="text-lg font-bold text-slate-800">94.8%</span>
          </div>
          <Scale size={20} className="text-[#0284C7]" />
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Critical Anomalies</span>
            <span className="text-lg font-bold text-red-600">3 Cases</span>
          </div>
          <ShieldAlert size={20} className="text-red-500" />
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Status filters */}
        <div className="flex gap-1.5 border-b border-slate-100 md:border-b-0 pb-2 md:pb-0 overflow-x-auto">
          {(['All', 'Healthy', 'Warning', 'Critical'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded text-xs font-semibold whitespace-nowrap transition-colors ${
                filter === s 
                  ? 'bg-[#E0F2FE] text-[#0369A1]' 
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full md:w-64">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search district..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-8 pl-9 pr-4 border border-slate-200 rounded text-xs focus:outline-none focus:border-sky-500 text-slate-700"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
        <h3 className="font-bold text-slate-800 text-sm md:text-base">District-wise Allocation & Activity</h3>
        <div className="overflow-x-auto border border-slate-100 rounded-lg">
          <table className="w-full text-left border-collapse text-xs md:text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold tracking-wider text-[10px] uppercase">
                <th className="py-3 px-4 font-bold">District Name</th>
                <th className="py-3 px-4 font-bold">FPS Centers</th>
                <th className="py-3 px-4 font-bold">Distributions Volume</th>
                <th className="py-3 px-4 font-bold">Total Transactions</th>
                <th className="py-3 px-4 font-bold">Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredDistricts.map((d) => (
                <tr key={d.name} className="border-b border-slate-50 hover:bg-slate-50/70 transition-colors text-slate-700">
                  <td className="py-3 px-4 font-bold text-slate-800">{d.name}</td>
                  <td className="py-3 px-4 tabular-nums">{d.fpsCenters}</td>
                  <td className="py-3 px-4 font-semibold tabular-nums">{d.distributionsKg.toLocaleString()} kg</td>
                  <td className="py-3 px-4 tabular-nums">{d.transactions.toLocaleString()}</td>
                  <td className="py-3 px-4">
                    <StatusBadge type={d.status} text={d.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
