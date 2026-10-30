import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { 
  Database, 
  TrendingUp, 
  AlertOctagon, 
  Archive, 
  PlusCircle, 
  X, 
  CheckCircle2, 
  Check,
  RotateCcw, 
  Wheat, 
  Flame, 
  Sparkles, 
  Calendar, 
  Truck, 
  AlertTriangle,
  ArrowRight,
  FileDown,
  Building2,
  ShieldCheck
} from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { mockInventory } from '../data/mockData';
import { Inventory as InventoryType } from '../types';

export const Inventory: React.FC = () => {
  const [inventoryList, setInventoryList] = useState<InventoryType[]>(mockInventory);

  // Modal and toast states
  const [isRestockModalOpen, setIsRestockModalOpen] = useState(false);
  const [selectedCommodity, setSelectedCommodity] = useState<InventoryType | null>(null);
  const [isFpsModalOpen, setIsFpsModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Restock Form State
  const [restockForm, setRestockForm] = useState({
    commodity: 'Rice' as 'Rice' | 'Wheat' | 'Sugar' | 'Kerosene',
    quantityKg: 50000,
    sourceSilo: 'FCI Godown #12 (Central Grain Reserve)',
    batchChallan: `FCI-CH-${Math.floor(1000 + Math.random() * 9000)}`,
    inspector: 'P. K. Verma (Logistics Controller)'
  });

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleOpenRestock = (commodityName?: 'Rice' | 'Wheat' | 'Sugar' | 'Kerosene') => {
    setRestockForm({
      commodity: commodityName || 'Rice',
      quantityKg: 50000,
      sourceSilo: 'FCI Godown #12 (Central Grain Reserve)',
      batchChallan: `FCI-CH-${Math.floor(1000 + Math.random() * 9000)}`,
      inspector: 'P. K. Verma (Logistics Controller)'
    });
    setIsRestockModalOpen(true);
  };

  const handleRestockSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const qty = Number(restockForm.quantityKg) || 0;
    if (qty <= 0) return;

    setInventoryList(prev => prev.map(item => {
      if (item.commodity === restockForm.commodity) {
        return {
          ...item,
          totalStockKg: item.totalStockKg + qty,
          lastStockRefill: new Date().toISOString().split('T')[0],
          lowStockFpsCount: Math.max(0, item.lowStockFpsCount - 2)
        };
      }
      return item;
    }));

    setIsRestockModalOpen(false);
    showToast(`Restocked ${qty.toLocaleString()} kg of ${restockForm.commodity} from ${restockForm.sourceSilo}!`);
  };

  const handleInspectFps = (item: InventoryType) => {
    setSelectedCommodity(item);
    setIsFpsModalOpen(true);
  };

  const handleDispatchEmergency = (commodity: string) => {
    setInventoryList(prev => prev.map(item => {
      if (item.commodity === commodity) {
        return {
          ...item,
          lowStockFpsCount: Math.max(0, item.lowStockFpsCount - 4)
        };
      }
      return item;
    }));
    setIsFpsModalOpen(false);
    showToast(`Emergency replenishment buffer dispatched for ${commodity}!`);
  };

  const handleExportInventory = () => {
    const headers = "Commodity,Total Stock (kg),Allocated Quota (kg),Available Buffer (kg),Low Stock FPS Centers,Last Restock Date\n";
    const rows = inventoryList.map(item => 
      `"${item.commodity}",${item.totalStockKg},${item.allocatedKg},${item.totalStockKg - item.allocatedKg},${item.lowStockFpsCount},"${item.lastStockRefill}"`
    ).join("\n");
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `inventory-report-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    showToast("Inventory report exported as CSV");
  };

  // Dynamic calculations
  const totalStockKg = inventoryList.reduce((acc, item) => acc + item.totalStockKg, 0);
  const totalAllocatedKg = inventoryList.reduce((acc, item) => acc + item.allocatedKg, 0);
  const totalLowStockFps = inventoryList.reduce((acc, item) => acc + item.lowStockFpsCount, 0);

  // Commodity visual configuration
  const getCommodityTheme = (name: string) => {
    switch (name) {
      case 'Rice':
        return {
          icon: <Wheat size={22} className="text-[#14654a]" />,
          bgPill: 'bg-[#14654a]/12 text-[#14654a]',
          barGradient: 'bg-gradient-to-r from-[#062d22] via-[#14654a] to-[#2fa56f]',
          accentBorder: 'hover:border-[#2fa56f]/40',
          desc: 'NFSA Fortified Grade A Paddy'
        };
      case 'Wheat':
        return {
          icon: <Wheat size={22} className="text-amber-700" />,
          bgPill: 'bg-amber-500/12 text-amber-800',
          barGradient: 'bg-gradient-to-r from-amber-700 via-amber-600 to-amber-400',
          accentBorder: 'hover:border-amber-400/40',
          desc: 'High-Gluten Milling Wheat Standard'
        };
      case 'Sugar':
        return {
          icon: <Sparkles size={22} className="text-cyan-700" />,
          bgPill: 'bg-cyan-500/12 text-cyan-800',
          barGradient: 'bg-gradient-to-r from-cyan-700 via-cyan-600 to-cyan-400',
          accentBorder: 'hover:border-cyan-400/40',
          desc: 'Refined White Crystalline Sugar (S-30)'
        };
      case 'Kerosene':
      default:
        return {
          icon: <Flame size={22} className="text-violet-700" />,
          bgPill: 'bg-violet-500/12 text-violet-800',
          barGradient: 'bg-gradient-to-r from-violet-800 via-violet-600 to-[#5b3df5]',
          accentBorder: 'hover:border-violet-400/40',
          desc: 'Subsidized Blue PDS Fuel Oil'
        };
    }
  };

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
              Inventory & Buffer Reserves
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase bg-[#2fa56f]/15 text-[#0d6840] border border-[#2fa56f]/30 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2fa56f] animate-pulse"></span>
              FCI Silo Sync
            </span>
          </div>
          <p className="text-xs md:text-sm text-[#5d7468] mt-1 font-medium">
            Monitor central foodgrain reserves, buffer stock quotas, replenishment pipelines, and FPS shortages.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5 self-start sm:self-center">
          <button
            type="button"
            onClick={handleExportInventory}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full border border-slate-200/80 bg-white/80 hover:bg-white text-xs md:text-sm font-bold text-[#10261c] shadow-xs transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          >
            <FileDown size={15} className="text-[#5d7468]" />
            <span>Export Report</span>
          </button>

          <button
            type="button"
            onClick={() => handleOpenRestock()}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full font-bold text-xs md:text-sm shadow-md transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] cursor-pointer !text-white text-white shrink-0"
            style={{
              background: 'linear-gradient(135deg, #14654a 0%, #1ea368 50%, #2fa56f 100%)',
              color: '#ffffff',
              boxShadow: '0 8px 20px -4px rgba(20, 101, 74, 0.4)'
            }}
          >
            <PlusCircle size={16} color="#ffffff" strokeWidth={2.4} className="shrink-0 text-white" />
            <span style={{ color: '#ffffff' }} className="font-bold text-white whitespace-nowrap">Refill Stock / Restock</span>
          </button>
        </div>
      </div>

      {/* 4 Redesigned Glass KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Stock */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Total Stock</span>
            <div className="w-8 h-8 rounded-full bg-[#14654a]/12 flex items-center justify-center text-[#14654a]">
              <Database size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              {totalStockKg.toLocaleString(undefined, { maximumFractionDigits: 1 })} kg
            </span>
            <span className="text-[11px] font-bold text-[#0d6840]">
              88% of target
            </span>
          </div>
        </div>

        {/* Card 2: Allocated Stock */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Allocated Quota</span>
            <div className="w-8 h-8 rounded-full bg-[#2fa56f]/15 flex items-center justify-center text-[#14654a]">
              <TrendingUp size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#14654a] font-display">
              {totalAllocatedKg.toLocaleString(undefined, { maximumFractionDigits: 1 })} kg
            </span>
            <span className="text-[11px] font-bold text-[#14654a] flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2fa56f] animate-pulse"></span>
              Committed
            </span>
          </div>
        </div>

        {/* Card 3: Low-Stock FPS */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Low-Stock FPS</span>
            <div className="w-8 h-8 rounded-full bg-[#ef5b4a]/15 flex items-center justify-center text-[#ef5b4a]">
              <AlertOctagon size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#ef5b4a] font-display">
              {totalLowStockFps} centers
            </span>
            <span className="text-[11px] font-bold text-[#ef5b4a] bg-[#ef5b4a]/10 px-2 py-0.5 rounded-full">
              Action required
            </span>
          </div>
        </div>

        {/* Card 4: Active Commodities */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Active Commodities</span>
            <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-slate-700">
              <Archive size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              {inventoryList.length} Types
            </span>
            <span className="text-[11px] font-bold text-[#14654a]">
              All pipelines live
            </span>
          </div>
        </div>
      </div>

      {/* Commodity Breakdown Cards (Grid of 4) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {inventoryList.map((item) => {
          const theme = getCommodityTheme(item.commodity);
          const percentUsed = Math.min(100, Math.round((item.allocatedKg / item.totalStockKg) * 100));
          const availableStock = Math.max(0, item.totalStockKg - item.allocatedKg);

          return (
            <div 
              key={item.commodity} 
              className={`bg-white/85 backdrop-blur-xl border border-white/90 rounded-[28px] p-6 shadow-sm hover:shadow-md transition-all duration-300 flex flex-col justify-between gap-4.5 ${theme.accentBorder}`}
            >
              {/* Card Header */}
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-3">
                  <div className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 ${theme.bgPill}`}>
                    {theme.icon}
                  </div>
                  <div>
                    <h3 className="font-extrabold text-[#10261c] text-lg leading-tight font-display">
                      {item.commodity}
                    </h3>
                    <p className="text-[11px] text-[#7a8b84] font-medium mt-0.5">
                      {theme.desc}
                    </p>
                  </div>
                </div>

                <div 
                  onClick={() => handleInspectFps(item)}
                  className="cursor-pointer group"
                >
                  <StatusBadge 
                    type={item.lowStockFpsCount > 8 ? 'High' : 'Low'} 
                    text={`${item.lowStockFpsCount} low stock centers`} 
                  />
                </div>
              </div>

              {/* Progress Bar & Stock Burn Rate */}
              <div className="space-y-1.5 pt-1">
                <div className="flex justify-between text-xs font-bold text-[#5d7468]">
                  <span className="uppercase tracking-wide text-[10.5px]">Stock Burn Rate</span>
                  <span className="text-[#10261c] font-bold">{percentUsed}% Allocated</span>
                </div>
                <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden p-0.5">
                  <div 
                    className={`h-full rounded-full transition-all duration-700 ${theme.barGradient}`} 
                    style={{ width: `${percentUsed}%` }}
                  />
                </div>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 gap-3.5 bg-slate-50/80 p-4 rounded-2xl border border-slate-100/90 text-xs">
                <div>
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wider block">
                    Total Silo Reserve
                  </span>
                  <strong className="text-sm font-extrabold text-[#10261c] tabular-nums font-display mt-0.5 block">
                    {item.totalStockKg.toLocaleString()} kg
                  </strong>
                </div>

                <div>
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wider block">
                    Allocated Quota
                  </span>
                  <strong className="text-sm font-extrabold text-[#14654a] tabular-nums font-display mt-0.5 block">
                    {item.allocatedKg.toLocaleString()} kg
                  </strong>
                </div>

                <div className="pt-2 border-t border-slate-200/50">
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wider block">
                    Available Balance
                  </span>
                  <strong className="text-xs font-bold text-[#10261c] tabular-nums mt-0.5 block">
                    {availableStock.toLocaleString()} kg
                  </strong>
                </div>

                <div className="pt-2 border-t border-slate-200/50">
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wider block">
                    Last Restocked
                  </span>
                  <span className="text-xs font-semibold text-[#5d7468] flex items-center gap-1 mt-0.5">
                    <Calendar size={12} />
                    {item.lastStockRefill}
                  </span>
                </div>
              </div>

              {/* Interactive Actions Footer */}
              <div className="flex items-center justify-between pt-1">
                <button
                  type="button"
                  onClick={() => handleInspectFps(item)}
                  className="inline-flex items-center gap-1.5 text-xs font-bold text-[#14654a] hover:text-[#0b5c39] transition-colors cursor-pointer"
                >
                  <span>Inspect Low-Stock FPS</span>
                  <ArrowRight size={13} />
                </button>

                <button
                  type="button"
                  onClick={() => handleOpenRestock(item.commodity)}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold bg-[#14654a]/12 text-[#14654a] hover:bg-[#14654a] hover:text-white transition-all duration-200 cursor-pointer"
                >
                  <RotateCcw size={12} />
                  <span>Refill Stock</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* =====================================================================
          LUXURY RESTOCK COMMODITY BATCH MODAL
          ===================================================================== */}
      {isRestockModalOpen && createPortal(
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setIsRestockModalOpen(false)}
        >
          <div 
            className="w-full max-w-[560px] rounded-[32px] overflow-hidden flex flex-col bg-white border border-slate-100 shadow-[0_24px_70px_-12px_rgba(16,38,28,0.3)] animate-in zoom-in-95 duration-200"
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
                  <Truck size={22} className="text-white" strokeWidth={2.2} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-extrabold text-[#10261c] text-lg font-display tracking-tight">
                      Replenish Buffer Stock
                    </h3>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-[#2fa56f]/15 text-[#0d6840] border border-[#2fa56f]/30">
                      FCI Intake
                    </span>
                  </div>
                  <p className="text-xs text-[#5d7468] mt-0.5 font-medium">
                    Log consignment inflow into state foodgrain silos
                  </p>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => setIsRestockModalOpen(false)} 
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-800 bg-slate-100/80 hover:bg-slate-200/80 transition-all shrink-0 cursor-pointer hover:rotate-90 duration-200"
                aria-label="Close dialog"
              >
                <X size={16} strokeWidth={2.2} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleRestockSubmit} className="p-7 space-y-4 text-xs md:text-sm">
              {/* Step 1: Interactive Commodity Selector Chips */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                  Select Commodity to Restock *
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {[
                    { name: 'Rice', label: 'Rice', sub: 'Gr. A Paddy', icon: <Wheat size={16} className="text-[#14654a]" /> },
                    { name: 'Wheat', label: 'Wheat', sub: 'Std. Milling', icon: <Wheat size={16} className="text-amber-700" /> },
                    { name: 'Sugar', label: 'Sugar', sub: 'Refined S-30', icon: <Sparkles size={16} className="text-cyan-700" /> },
                    { name: 'Kerosene', label: 'Kerosene', sub: 'PDS Blue Fuel', icon: <Flame size={16} className="text-violet-700" /> }
                  ].map((item) => {
                    const isSelected = restockForm.commodity === item.name;
                    return (
                      <button
                        key={item.name}
                        type="button"
                        onClick={() => setRestockForm({ ...restockForm, commodity: item.name as any })}
                        className={`relative p-2.5 rounded-2xl flex flex-col items-center justify-center text-center transition-all cursor-pointer border ${
                          isSelected
                            ? 'bg-[#14654a]/8 border-[#14654a] shadow-xs'
                            : 'bg-slate-50/70 border-slate-200/80 hover:bg-white hover:border-slate-300'
                        }`}
                      >
                        {isSelected && (
                          <span className="absolute top-1.5 right-1.5 w-4 h-4 rounded-full bg-[#14654a] text-white flex items-center justify-center">
                            <Check size={10} strokeWidth={3} />
                          </span>
                        )}
                        <div className="mb-1">{item.icon}</div>
                        <span className={`text-xs font-extrabold ${isSelected ? 'text-[#14654a]' : 'text-[#10261c]'}`}>
                          {item.label}
                        </span>
                        <span className="text-[10px] text-[#7a8b84] font-medium truncate max-w-full">
                          {item.sub}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Step 2: Inflow Volume & Quick Presets */}
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                    Restock Inflow Volume *
                  </label>
                  <span className="text-[11px] font-bold text-[#14654a]">
                    ≈ {((restockForm.quantityKg || 0) / 1000).toLocaleString()} MT (Metric Tonnes)
                  </span>
                </div>
                
                <div className="relative">
                  <input
                    type="number"
                    min="1000"
                    step="1000"
                    required
                    value={restockForm.quantityKg}
                    onChange={(e) => setRestockForm({ ...restockForm, quantityKg: Number(e.target.value) })}
                    className="w-full pl-4 pr-16 py-3 border border-slate-200/90 rounded-2xl text-base font-extrabold text-[#10261c] bg-white focus:outline-none focus:border-[#14654a] focus:ring-3 focus:ring-[#14654a]/15 transition-all font-display [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                    placeholder="Enter weight in kg"
                  />
                  <div className="absolute right-3.5 top-1/2 -translate-y-1/2">
                    <span className="text-xs font-extrabold text-[#14654a] bg-[#14654a]/10 px-2.5 py-1 rounded-lg">
                      KG
                    </span>
                  </div>
                </div>

                {/* Quick Presets */}
                <div className="flex items-center gap-2 pt-1 flex-wrap">
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wider">Quick Fill:</span>
                  {[25000, 50000, 100000, 250000].map(amt => (
                    <button
                      key={amt}
                      type="button"
                      onClick={() => setRestockForm({ ...restockForm, quantityKg: amt })}
                      className={`px-3 py-1 rounded-full text-[11px] font-bold transition-all cursor-pointer ${
                        restockForm.quantityKg === amt 
                          ? 'bg-[#14654a] text-white shadow-xs scale-[1.03]' 
                          : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                      }`}
                    >
                      +{(amt / 1000).toLocaleString()}k kg
                    </button>
                  ))}
                </div>
              </div>

              {/* Step 3: Logistics & Verified Credentials Card */}
              <div className="p-4 rounded-2xl bg-slate-50/80 border border-slate-200/80 space-y-3">
                <div className="flex items-center justify-between pb-1 border-b border-slate-200/50">
                  <span className="text-[10.5px] font-bold text-[#7a8b84] uppercase tracking-wider flex items-center gap-1.5">
                    <Building2 size={13} className="text-[#14654a]" />
                    FCI Logistics & Consignment Info
                  </span>
                  <span className="text-[10px] font-bold text-emerald-800 bg-emerald-100/70 border border-emerald-300/60 px-2 py-0.5 rounded-full flex items-center gap-1">
                    <ShieldCheck size={11} className="text-emerald-700" /> Auto-Verified
                  </span>
                </div>

                <div className="space-y-1">
                  <label className="text-[10.5px] font-bold text-[#5d7468] uppercase tracking-wide block">
                    Origin Warehouse / Silo
                  </label>
                  <input
                    type="text"
                    value={restockForm.sourceSilo}
                    onChange={(e) => setRestockForm({ ...restockForm, sourceSilo: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200/90 rounded-xl text-xs font-semibold text-[#10261c] bg-white focus:outline-none focus:border-[#14654a] focus:ring-2 focus:ring-[#14654a]/15 transition-all"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[10.5px] font-bold text-[#5d7468] uppercase tracking-wide block">
                      Batch Challan No.
                    </label>
                    <input
                      type="text"
                      value={restockForm.batchChallan}
                      onChange={(e) => setRestockForm({ ...restockForm, batchChallan: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-200/90 rounded-xl text-xs font-mono font-bold text-[#10261c] bg-slate-100/90"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10.5px] font-bold text-[#5d7468] uppercase tracking-wide block">
                      Authorized Inspector
                    </label>
                    <input
                      type="text"
                      value={restockForm.inspector}
                      onChange={(e) => setRestockForm({ ...restockForm, inspector: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-200/90 rounded-xl text-xs font-semibold text-[#10261c] bg-white focus:outline-none focus:border-[#14654a] focus:ring-2 focus:ring-[#14654a]/15 transition-all"
                    />
                  </div>
                </div>
              </div>

              {/* Step 4: Refill Impact Ribbon */}
              <div className="flex items-center justify-between p-3 rounded-2xl bg-gradient-to-r from-emerald-500/10 via-[#14654a]/5 to-transparent border border-emerald-500/20">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-full bg-[#14654a]/15 text-[#14654a] flex items-center justify-center shrink-0">
                    <TrendingUp size={14} />
                  </div>
                  <div className="text-xs">
                    <span className="font-bold text-[#10261c]">Reserve Inflow: </span>
                    <span className="text-[#5d7468]">
                      +{(restockForm.quantityKg || 0).toLocaleString()} kg to {restockForm.commodity} Buffer
                    </span>
                  </div>
                </div>
                <span className="text-[11px] font-extrabold text-[#14654a] bg-white px-2.5 py-0.5 rounded-full shadow-xs border border-emerald-200">
                  +{((restockForm.quantityKg || 0) / 1000).toFixed(0)} MT
                </span>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsRestockModalOpen(false)}
                  className="px-5 py-2.5 rounded-full text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full text-xs md:text-sm font-bold shadow-md transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
                  style={{
                    background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
                    color: '#ffffff',
                    boxShadow: '0 8px 18px -4px rgba(20, 101, 74, 0.45)'
                  }}
                >
                  <PlusCircle size={16} className="text-white" strokeWidth={2.4} />
                  <span style={{ color: '#ffffff' }}>Confirm Inflow & Refill</span>
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}

      {/* =====================================================================
          LOW-STOCK FPS INSPECTION DRAWER / MODAL
          ===================================================================== */}
      {isFpsModalOpen && selectedCommodity && createPortal(
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setIsFpsModalOpen(false)}
        >
          <div 
            className="w-full max-w-[560px] rounded-[32px] overflow-hidden flex flex-col bg-white border border-slate-100 shadow-[0_24px_70px_-12px_rgba(239,91,74,0.25)] animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-7 py-5 border-b border-red-100/60 bg-gradient-to-b from-red-50/70 to-white">
              <div className="flex items-center gap-3.5 flex-1 min-w-0 pr-3">
                <div className="w-12 h-12 rounded-2xl bg-red-100 text-red-600 flex items-center justify-center shrink-0 shadow-md shadow-red-500/10">
                  <AlertTriangle size={22} strokeWidth={2.2} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-extrabold text-[#10261c] text-lg font-display tracking-tight truncate">
                      {selectedCommodity.commodity} Shortage Centers
                    </h3>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-red-100 text-red-700 border border-red-200">
                      Alert
                    </span>
                  </div>
                  <p className="text-xs text-[#5d7468] mt-0.5 font-medium">
                    {selectedCommodity.lowStockFpsCount} FPS centers below 15% safety threshold
                  </p>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => setIsFpsModalOpen(false)} 
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-800 bg-slate-100/80 hover:bg-slate-200/80 transition-all shrink-0 cursor-pointer hover:rotate-90 duration-200"
                aria-label="Close dialog"
              >
                <X size={16} strokeWidth={2.2} />
              </button>
            </div>

            {/* List of Affected FPS */}
            <div className="p-7 space-y-4 text-xs md:text-sm">
              <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                {[
                  { id: 'FPS-DL-0042', district: 'East Delhi', stockKg: 450, burnDays: '2.1 days remaining' },
                  { id: 'FPS-LU-0089', district: 'Lucknow', stockKg: 620, burnDays: '2.8 days remaining' },
                  { id: 'FPS-GW-0014', district: 'Gwalior', stockKg: 380, burnDays: '1.7 days remaining' },
                  { id: 'FPS-AB-0099', district: 'Aurangabad', stockKg: 510, burnDays: '2.4 days remaining' }
                ].map((fps) => (
                  <div key={fps.id} className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-50/80 border border-slate-100/90 hover:bg-slate-50 transition-colors">
                    <div>
                      <span className="font-mono font-bold text-[#10261c] block text-xs">{fps.id}</span>
                      <span className="text-[11px] text-[#7a8b84] font-medium">{fps.district}</span>
                    </div>
                    <div className="text-right">
                      <span className="font-bold text-red-600 block">{fps.stockKg} kg left</span>
                      <span className="text-[10.5px] text-[#ef5b4a] font-bold bg-red-100/70 px-2 py-0.5 rounded-full inline-block mt-0.5">
                        {fps.burnDays}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Actions */}
              <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsFpsModalOpen(false)}
                  className="px-5 py-2.5 rounded-full text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Close
                </button>
                <button
                  type="button"
                  onClick={() => handleDispatchEmergency(selectedCommodity.commodity)}
                  className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full text-xs md:text-sm font-bold text-white shadow-md transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
                  style={{
                    background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
                    boxShadow: '0 8px 18px -4px rgba(20, 101, 74, 0.45)'
                  }}
                >
                  <Truck size={16} className="text-white" />
                  <span>Dispatch Emergency Buffer Stock</span>
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
