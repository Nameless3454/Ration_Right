import React from 'react';
import { Database, TrendingUp, AlertOctagon, Archive } from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { mockInventory } from '../data/mockData';

export const Inventory: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">Inventory</h1>
        <p className="text-xs md:text-sm text-slate-500 mt-1">
          Monitor commodity stocks, safety reserve levels, and low-inventory alerts.
        </p>
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Total Stock</span>
            <span className="text-lg font-bold text-slate-800">79,61,167.9 kg</span>
          </div>
          <Database size={20} className="text-[#0284C7]" />
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Allocated Stock</span>
            <span className="text-lg font-bold text-green-600">70,00,000.0 kg</span>
          </div>
          <TrendingUp size={20} className="text-green-500" />
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Low-Stock FPS</span>
            <span className="text-lg font-bold text-red-600">39 centers</span>
          </div>
          <AlertOctagon size={20} className="text-red-500" />
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 font-bold block uppercase">Active Commodities</span>
            <span className="text-lg font-bold text-slate-800">4 Types</span>
          </div>
          <Archive size={20} className="text-[#0284C7]" />
        </div>
      </div>

      {/* Commodity Breakdown Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {mockInventory.map((item) => {
          const percentUsed = Math.round((item.allocatedKg / item.totalStockKg) * 100);
          return (
            <div key={item.commodity} className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col gap-3">
              <div className="flex justify-between items-center">
                <span className="font-bold text-slate-800 text-sm md:text-base">{item.commodity}</span>
                <StatusBadge 
                  type={item.lowStockFpsCount > 10 ? 'High' : 'Low'} 
                  text={`${item.lowStockFpsCount} low stock centers`} 
                />
              </div>

              {/* Progress bar */}
              <div>
                <div className="flex justify-between text-xs font-semibold text-slate-500 mb-1.5">
                  <span>Stock Burn Rate</span>
                  <span>{percentUsed}% Allocated</span>
                </div>
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                  <div 
                    className="bg-[#0284C7] h-full rounded-full transition-all duration-500" 
                    style={{ width: `${percentUsed}%` }}
                  />
                </div>
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-2 gap-3.5 mt-2 bg-slate-50 p-3 rounded border border-slate-100 text-xs text-slate-700">
                <div>
                  <span className="text-slate-400 font-medium block">Total Stock</span>
                  <strong className="text-slate-800 font-bold tabular-nums">{item.totalStockKg.toLocaleString()} kg</strong>
                </div>
                <div>
                  <span className="text-slate-400 font-medium block">Allocated Limit</span>
                  <strong className="text-slate-800 font-bold tabular-nums">{item.allocatedKg.toLocaleString()} kg</strong>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
