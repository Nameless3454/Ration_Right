import React, { useState, useMemo } from 'react';
import { 
  ComposedChart, 
  Bar, 
  Line, 
  Area,
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  ReferenceLine
} from 'recharts';
import { 
  TrendingUp, 
  Calendar, 
  FileDown, 
  RotateCcw, 
  Sparkles, 
  ShieldCheck, 
  Database, 
  Activity,
  CheckCircle2,
  X,
  Store,
  Scale
} from 'lucide-react';

interface DataPoint {
  date: string;
  availableInventory: number;
  stockWithdrawn: number;
  targetThreshold: number;
  replenished?: boolean;
}

export const Analytics: React.FC = () => {
  const [timeRange, setTimeRange] = useState<'7d' | '14d' | '30d'>('7d');
  const [selectedCommodity, setSelectedCommodity] = useState<'All' | 'Rice' | 'Wheat' | 'Sugar' | 'Kerosene'>('All');
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Multi-timeframe realistic telemetry datasets
  const data7d: DataPoint[] = [
    { date: 'Aug 01', availableInventory: 95000, stockWithdrawn: 14500, targetThreshold: 35000 },
    { date: 'Aug 02', availableInventory: 80500, stockWithdrawn: 16210, targetThreshold: 35000 },
    { date: 'Aug 03', availableInventory: 64290, stockWithdrawn: 13890, targetThreshold: 35000 },
    { date: 'Aug 04', availableInventory: 50400, stockWithdrawn: 17765, targetThreshold: 35000 },
    { date: 'Aug 05', availableInventory: 32635, stockWithdrawn: 18980, targetThreshold: 35000 },
    { date: 'Aug 06', availableInventory: 110000, stockWithdrawn: 15420, targetThreshold: 35000, replenished: true }, // FCI Silo Restock
    { date: 'Aug 07', availableInventory: 94580, stockWithdrawn: 16900, targetThreshold: 35000 }
  ];

  const data14d: DataPoint[] = [
    { date: 'Jul 25', availableInventory: 120000, stockWithdrawn: 13200, targetThreshold: 35000 },
    { date: 'Jul 26', availableInventory: 106800, stockWithdrawn: 14100, targetThreshold: 35000 },
    { date: 'Jul 27', availableInventory: 92700, stockWithdrawn: 15800, targetThreshold: 35000 },
    { date: 'Jul 28', availableInventory: 76900, stockWithdrawn: 16200, targetThreshold: 35000 },
    { date: 'Jul 29', availableInventory: 60700, stockWithdrawn: 14900, targetThreshold: 35000 },
    { date: 'Jul 30', availableInventory: 45800, stockWithdrawn: 17500, targetThreshold: 35000 },
    { date: 'Jul 31', availableInventory: 108000, stockWithdrawn: 13000, targetThreshold: 35000, replenished: true },
    ...data7d
  ];

  const data30d: DataPoint[] = [
    { date: 'Jul 09', availableInventory: 115000, stockWithdrawn: 14200, targetThreshold: 35000 },
    { date: 'Jul 12', availableInventory: 98000, stockWithdrawn: 15400, targetThreshold: 35000 },
    { date: 'Jul 15', availableInventory: 79000, stockWithdrawn: 16800, targetThreshold: 35000 },
    { date: 'Jul 18', availableInventory: 125000, stockWithdrawn: 13900, targetThreshold: 35000, replenished: true },
    { date: 'Jul 21', availableInventory: 111100, stockWithdrawn: 14800, targetThreshold: 35000 },
    { date: 'Jul 24', availableInventory: 96300, stockWithdrawn: 15900, targetThreshold: 35000 },
    ...data14d
  ];

  // Active dataset
  const activeDataset = useMemo(() => {
    const raw = timeRange === '7d' ? data7d : timeRange === '14d' ? data14d : data30d;
    
    // Scale by selected commodity if filtered
    const multiplier = 
      selectedCommodity === 'Rice' ? 0.54 :
      selectedCommodity === 'Wheat' ? 0.36 :
      selectedCommodity === 'Sugar' ? 0.08 :
      selectedCommodity === 'Kerosene' ? 0.02 : 1;

    return raw.map(d => ({
      ...d,
      availableInventory: Math.round(d.availableInventory * multiplier),
      stockWithdrawn: Math.round(d.stockWithdrawn * multiplier),
      targetThreshold: Math.round(d.targetThreshold * multiplier)
    }));
  }, [timeRange, selectedCommodity]);

  // Derived Metrics
  const totalWithdrawn = activeDataset.reduce((acc, d) => acc + d.stockWithdrawn, 0);
  const avgDailyWithdrawal = Math.round(totalWithdrawn / activeDataset.length);
  const currentInventory = activeDataset[activeDataset.length - 1].availableInventory;
  const daysRunway = (currentInventory / avgDailyWithdrawal).toFixed(1);

  const handleExportCSV = () => {
    const headers = "Date,Available Reserve (kg),Daily Withdrawal (kg),Safety Threshold (kg),Consignment Restocked\n";
    const rows = activeDataset.map(d => 
      `"${d.date}",${d.availableInventory},${d.stockWithdrawn},${d.targetThreshold},"${d.replenished ? 'Yes' : 'No'}"`
    ).join("\n");
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analytics-velocity-${timeRange}-${selectedCommodity.toLowerCase()}-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    showToast(`Analytics data for ${selectedCommodity} (${timeRange}) exported as CSV.`);
  };

  // Custom Ultra-Luxury Glass Tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const inventoryVal = payload.find((p: any) => p.dataKey === 'availableInventory')?.value || 0;
      const withdrawalVal = payload.find((p: any) => p.dataKey === 'stockWithdrawn')?.value || 0;
      const burnPct = inventoryVal > 0 ? ((withdrawalVal / inventoryVal) * 100).toFixed(1) : '0';

      return (
        <div className="bg-[#0b1f17]/95 backdrop-blur-xl border border-white/20 text-white p-4 rounded-2xl shadow-2xl min-w-[220px] space-y-2.5 animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-center justify-between border-b border-white/10 pb-2">
            <span className="text-xs font-extrabold text-white font-display flex items-center gap-1.5">
              <Calendar size={13} className="text-[#7fd8aa]" />
              {label}
            </span>
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#7fd8aa] bg-[#14654a]/40 px-2 py-0.5 rounded-full border border-[#2fa56f]/30">
              {burnPct}% Burn
            </span>
          </div>

          <div className="space-y-1.5 text-xs">
            {/* Line value: Available Inventory */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-300">
                <span className="w-2.5 h-2.5 rounded-full bg-[#2fa56f] shadow-[0_0_8px_#2fa56f]"></span>
                <span className="text-[11px] font-medium">Available Reserve:</span>
              </div>
              <span className="font-extrabold text-white font-display">
                {Number(inventoryVal).toLocaleString()} kg
              </span>
            </div>

            {/* Bar value: Stock Taken */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-300">
                <span className="w-2.5 h-2.5 rounded-full bg-[#7fd8aa]"></span>
                <span className="text-[11px] font-medium">Daily Outflow:</span>
              </div>
              <span className="font-bold text-[#7fd8aa]">
                {Number(withdrawalVal).toLocaleString()} kg
              </span>
            </div>
          </div>

          <div className="pt-2 border-t border-white/10 text-[10px] text-slate-400 flex items-center justify-between">
            <span>Buffer Margin:</span>
            <span className="text-emerald-400 font-bold">
              +{(inventoryVal / 1000).toFixed(0)} Metric Tonnes
            </span>
          </div>
        </div>
      );
    }
    return null;
  };

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
              Analytics & Reserve Dynamics
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase bg-[#2fa56f]/15 text-[#0d6840] border border-[#2fa56f]/30 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2fa56f] animate-pulse"></span>
              Live Telemetry
            </span>
          </div>
          <p className="text-xs md:text-sm text-[#5d7468] mt-1 font-medium">
            Real-time stock withdrawal velocity, foodgrain depletion trajectories, and buffer safety margins.
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
            <span>Export Analytics CSV</span>
          </button>

          <button
            type="button"
            onClick={() => showToast('Analytics pipeline refreshed with real-time FCI telemetry.')}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full font-bold text-xs md:text-sm shadow-md transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] cursor-pointer !text-white text-white shrink-0"
            style={{
              background: 'linear-gradient(135deg, #14654a 0%, #1ea368 50%, #2fa56f 100%)',
              color: '#ffffff',
              boxShadow: '0 8px 20px -4px rgba(20, 101, 74, 0.4)'
            }}
          >
            <RotateCcw size={15} className="text-white" />
            <span className="font-bold text-white">Sync Feed</span>
          </button>
        </div>
      </div>

      {/* 4 Luxury KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Current Inventory */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Available Reserve</span>
            <div className="w-8 h-8 rounded-full bg-[#14654a]/12 flex items-center justify-center text-[#14654a]">
              <Database size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              {currentInventory.toLocaleString()} kg
            </span>
            <span className="text-[11px] font-bold text-[#0d6840]">
              {(currentInventory / 1000).toFixed(0)} MT in silo
            </span>
          </div>
        </div>

        {/* Card 2: Total Outflow */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Period Withdrawal</span>
            <div className="w-8 h-8 rounded-full bg-cyan-500/15 flex items-center justify-center text-cyan-700">
              <TrendingUp size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              {totalWithdrawn.toLocaleString()} kg
            </span>
            <span className="text-[11px] font-bold text-cyan-700">
              {timeRange} cumulative
            </span>
          </div>
        </div>

        {/* Card 3: Daily Burn Rate */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Avg. Daily Burn</span>
            <div className="w-8 h-8 rounded-full bg-amber-500/15 flex items-center justify-center text-amber-700">
              <Activity size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              {avgDailyWithdrawal.toLocaleString()} kg/d
            </span>
            <span className="text-[11px] font-bold text-amber-700">
              Normal Velocity
            </span>
          </div>
        </div>

        {/* Card 4: Runway Days */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Safety Runway</span>
            <div className="w-8 h-8 rounded-full bg-emerald-500/15 flex items-center justify-center text-[#14654a]">
              <ShieldCheck size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#14654a] font-display">
              {daysRunway} Days
            </span>
            <span className="text-[11px] font-bold text-[#14654a] bg-emerald-100/70 px-2 py-0.5 rounded-full">
              Silo Safe
            </span>
          </div>
        </div>
      </div>

      {/* Main Luxury Chart Container */}
      <div className="bg-white/95 backdrop-blur-2xl border border-white/90 rounded-[32px] p-6 md:p-8 shadow-sm space-y-6">
        {/* Chart Top Controls & Commodity Tabs */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2.5">
              <h3 className="font-extrabold text-[#10261c] text-lg md:text-xl font-display tracking-tight">
                Stock Withdrawal vs. Available Buffer Inventory
              </h3>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-100/70 text-emerald-800 border border-emerald-200">
                Dual Axis Telemetry
              </span>
            </div>
            <p className="text-xs text-[#5d7468] mt-1 font-medium">
              Line denotes available central silo stock (left scale, kg) vs. daily citizen withdrawals (bar pillars, right scale, kg).
            </p>
          </div>

          {/* Timeframe & Commodity Filter Toolbar */}
          <div className="flex items-center gap-3 flex-wrap">
            {/* Commodity Filter Tabs */}
            <div className="flex items-center gap-1 bg-slate-100/80 p-1 rounded-full border border-slate-200/60">
              {(['All', 'Rice', 'Wheat', 'Sugar', 'Kerosene'] as const).map(c => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setSelectedCommodity(c)}
                  className={`px-3 py-1 rounded-full text-xs font-bold transition-all cursor-pointer ${
                    selectedCommodity === c
                      ? 'bg-white text-[#10261c] shadow-xs'
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>

            {/* Timeframe Range Tabs */}
            <div className="flex items-center gap-1 bg-[#14654a]/8 p-1 rounded-full border border-[#14654a]/20">
              {(['7d', '14d', '30d'] as const).map(r => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setTimeRange(r)}
                  className={`px-3 py-1 rounded-full text-xs font-bold transition-all cursor-pointer ${
                    timeRange === r
                      ? 'bg-[#14654a] text-white shadow-xs'
                      : 'text-[#14654a] hover:bg-[#14654a]/10'
                  }`}
                >
                  {r.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* The Motion Chart Canvas */}
        <div className="h-[380px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={activeDataset}
              margin={{ top: 20, right: 25, left: 15, bottom: 10 }}
            >
              {/* Ultra-Luxury SVG Gradients and Glow Filters */}
              <defs>
                {/* Emerald Gradient for Bar Outflow */}
                <linearGradient id="barGradientOutflow" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2fa56f" stopOpacity={0.95} />
                  <stop offset="60%" stopColor="#14654a" stopOpacity={0.85} />
                  <stop offset="100%" stopColor="#062d22" stopOpacity={0.7} />
                </linearGradient>

                {/* Soft Mint Area Gradient under the Inventory curve */}
                <linearGradient id="areaGradientInventory" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2fa56f" stopOpacity={0.28} />
                  <stop offset="50%" stopColor="#7fd8aa" stopOpacity={0.12} />
                  <stop offset="100%" stopColor="#14654a" stopOpacity={0.0} />
                </linearGradient>

                {/* Glowing drop shadow filter */}
                <filter id="emeraldGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="#2fa56f" floodOpacity="0.35" />
                </filter>
              </defs>

              {/* Gentle, minimal grid lines */}
              <CartesianGrid 
                strokeDasharray="4 4" 
                stroke="#e2ece6" 
                vertical={false} 
              />

              {/* X Axis */}
              <XAxis 
                dataKey="date" 
                stroke="#7a8b84" 
                fontSize={12}
                fontWeight={600}
                tickLine={false}
                axisLine={{ stroke: '#e2ece6', strokeWidth: 1.5 }}
                dy={8}
              />

              {/* Left Y Axis: Available Inventory */}
              <YAxis 
                yAxisId="left" 
                stroke="#14654a" 
                fontSize={11}
                fontWeight={700}
                tickLine={false}
                axisLine={false}
                tickFormatter={(val) => `${(val / 1000).toFixed(0)}k kg`}
                label={{ 
                  value: 'Silo Reserve Stock (kg)', 
                  angle: -90, 
                  position: 'insideLeft', 
                  offset: 0,
                  style: { textAnchor: 'middle', fill: '#14654a', fontSize: 11, fontWeight: '800' } 
                }} 
              />

              {/* Right Y Axis: Stock Taken */}
              <YAxis 
                yAxisId="right" 
                orientation="right" 
                stroke="#2fa56f" 
                fontSize={11}
                fontWeight={700}
                tickLine={false}
                axisLine={false}
                tickFormatter={(val) => `${(val / 1000).toFixed(0)}k`}
                label={{ 
                  value: 'Daily Withdrawal Velocity (kg)', 
                  angle: 90, 
                  position: 'insideRight', 
                  offset: 5,
                  style: { textAnchor: 'middle', fill: '#2fa56f', fontSize: 11, fontWeight: '800' } 
                }} 
              />

              {/* Custom Rich Tooltip */}
              <Tooltip 
                content={<CustomTooltip />}
                cursor={{ fill: 'rgba(20, 101, 74, 0.05)', radius: 8 }}
              />

              {/* Safety Margin Reference Line */}
              <ReferenceLine 
                yAxisId="left" 
                y={activeDataset[0]?.targetThreshold || 35000} 
                stroke="#f59e0b" 
                strokeDasharray="5 5" 
                strokeWidth={1.5}
                label={{ 
                  value: 'Safety Buffer Threshold', 
                  fill: '#d97706', 
                  fontSize: 10, 
                  fontWeight: '700', 
                  position: 'top' 
                }} 
              />

              {/* Area Layer: Soft ambient glow under inventory line */}
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="availableInventory"
                fill="url(#areaGradientInventory)"
                stroke="none"
                animationDuration={900}
                animationEasing="ease-out"
              />

              {/* Bar Layer: Rounded pill bars with lush gradient */}
              <Bar 
                yAxisId="right" 
                dataKey="stockWithdrawn" 
                name="Daily Citizen Withdrawal" 
                fill="url(#barGradientOutflow)" 
                radius={[10, 10, 3, 3]} 
                barSize={timeRange === '7d' ? 38 : timeRange === '14d' ? 22 : 12}
                animationDuration={1000}
                animationEasing="ease-out"
              />

              {/* Line Layer: Silo Stock Reserve Curve with glow and rich dots */}
              <Line 
                yAxisId="left" 
                type="monotone" 
                dataKey="availableInventory" 
                name="Available Silo Reserve" 
                stroke="#062d22" 
                strokeWidth={3.5} 
                dot={{ 
                  r: 4.5, 
                  fill: '#ffffff', 
                  stroke: '#14654a', 
                  strokeWidth: 2.5 
                }} 
                activeDot={{ 
                  r: 7, 
                  fill: '#2fa56f', 
                  stroke: '#ffffff', 
                  strokeWidth: 3,
                  style: { filter: 'drop-shadow(0 0 6px rgba(47, 165, 111, 0.8))' }
                }} 
                filter="url(#emeraldGlow)"
                animationDuration={1200}
                animationEasing="ease-out"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Chart Legend & Telemetry Insights Footer */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-4 border-t border-slate-100">
          <div className="flex items-center gap-5 flex-wrap">
            <div className="flex items-center gap-2 text-xs font-bold text-[#10261c]">
              <span className="w-3.5 h-3.5 rounded-md bg-gradient-to-b from-[#2fa56f] to-[#14654a] shadow-xs"></span>
              <span>Daily Citizen Withdrawal (Bar)</span>
            </div>
            <div className="flex items-center gap-2 text-xs font-bold text-[#10261c]">
              <span className="w-5 h-1 rounded-full bg-[#062d22] flex items-center justify-center">
                <span className="w-2 h-2 rounded-full bg-[#2fa56f] ring-2 ring-white"></span>
              </span>
              <span>Central Buffer Reserve (Curve)</span>
            </div>
            <div className="flex items-center gap-2 text-xs font-semibold text-amber-700">
              <span className="w-4 h-0.5 border-t-2 border-dashed border-amber-500"></span>
              <span>Buffer Safety Threshold (35k kg)</span>
            </div>
          </div>

          <div className="text-xs font-semibold text-[#5d7468] flex items-center gap-1.5 self-start sm:self-auto">
            <Sparkles size={14} className="text-[#14654a]" />
            <span>FCI consignment replenishment detected on Aug 06 (+77.3 MT)</span>
          </div>
        </div>
      </div>

      {/* =====================================================================
          EXPANDED ANALYTICS: DISTRICT VELOCITY & STOCKOUT PROJECTIONS
          ===================================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Card 1: District Outflow & Allocation Matrix */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[28px] p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-[#14654a]/12 flex items-center justify-center text-[#14654a]">
                  <TrendingUp size={16} />
                </div>
                <div>
                  <h3 className="font-extrabold text-[#10261c] text-sm md:text-base font-display">
                    Regional Outflow Velocity
                  </h3>
                  <p className="text-[11px] text-[#7a8b84] font-medium">October 2026 distribution metrics</p>
                </div>
              </div>
              <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
                3 Districts
              </span>
            </div>

            <div className="mt-4 space-y-3.5">
              {[
                { name: 'Ghaziabad', volume: 5150, cap: 14000, shops: 3, risk: 'Medium', note: '-280kg shortfall at PWD002' },
                { name: 'East Delhi', volume: 2600, cap: 5000, shops: 1, risk: 'Low', note: '100% quota compliance' },
                { name: 'Noida', volume: 1850, cap: 4500, shops: 1, risk: 'High', note: '-200kg shortfall, Audit Failed' }
              ].map((dist) => {
                const pct = Math.round((dist.volume / dist.cap) * 100);
                return (
                  <div key={dist.name} className="p-3 rounded-2xl bg-slate-50/70 border border-slate-200/60 hover:bg-white transition-all">
                    <div className="flex items-center justify-between text-xs font-bold text-[#10261c]">
                      <span className="flex items-center gap-1.5">
                        <span>{dist.name}</span>
                        <span className="text-[10px] text-slate-400 font-normal">({dist.shops} FPS)</span>
                      </span>
                      <span className="font-mono">{dist.volume.toLocaleString()} / {dist.cap.toLocaleString()} kg</span>
                    </div>
                    <div className="w-full h-2 bg-slate-200/60 rounded-full mt-2 overflow-hidden flex">
                      <div 
                        className={`h-full rounded-full transition-all duration-700 ${
                          dist.risk === 'High' ? 'bg-gradient-to-r from-rose-500 to-red-600' :
                          dist.risk === 'Medium' ? 'bg-gradient-to-r from-amber-500 to-amber-600' :
                          'bg-gradient-to-r from-[#14654a] to-[#2fa56f]'
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between mt-1.5 text-[10px]">
                      <span className="text-slate-500">{dist.note}</span>
                      <span className="font-bold text-slate-700">{pct}% utilized</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Aggregated Outflow:</span>
            <span className="font-bold text-[#10261c]">9,450 kg (40.2% Total Cap)</span>
          </div>
        </div>

        {/* Card 2: Commodity Breakdown & Quota Fill */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[28px] p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-blue-50 flex items-center justify-center text-blue-700">
                  <Scale size={16} />
                </div>
                <div>
                  <h3 className="font-extrabold text-[#10261c] text-sm md:text-base font-display">
                    Commodity Allocation Split
                  </h3>
                  <p className="text-[11px] text-[#7a8b84] font-medium">Grain-specific intake & disbursement</p>
                </div>
              </div>
              <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-800 border border-blue-200">
                PDS Quota
              </span>
            </div>

            <div className="mt-4 space-y-4">
              {/* Rice */}
              <div className="p-3.5 rounded-2xl bg-emerald-50/40 border border-emerald-100">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-extrabold text-[#10261c] flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#14654a]" />
                    Rice (Grade A Paddy)
                  </span>
                  <span className="font-bold text-[#14654a]">5,600 kg (59.3%)</span>
                </div>
                <div className="w-full h-2 bg-emerald-100/70 rounded-full mt-2 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-[#14654a] to-[#2fa56f] rounded-full" style={{ width: '59.3%' }} />
                </div>
                <div className="flex items-center justify-between mt-1 text-[10px] text-slate-500">
                  <span>Physical Stock: 2,825 kg</span>
                  <span className="text-rose-600 font-semibold">-480 kg Net Deficit (PWD002 & 004)</span>
                </div>
              </div>

              {/* Wheat */}
              <div className="p-3.5 rounded-2xl bg-amber-50/40 border border-amber-100">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-extrabold text-[#10261c] flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-600" />
                    Wheat (Standard Milling)
                  </span>
                  <span className="font-bold text-amber-800">3,850 kg (40.7%)</span>
                </div>
                <div className="w-full h-2 bg-amber-100/70 rounded-full mt-2 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-amber-500 to-amber-600 rounded-full" style={{ width: '40.7%' }} />
                </div>
                <div className="flex items-center justify-between mt-1 text-[10px] text-slate-500">
                  <span>Physical Stock: 3,245 kg</span>
                  <span className="text-emerald-700 font-semibold">-400 kg Natural Variance (Compliant)</span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Overall Stock Discrepancy:</span>
            <span className="font-bold text-rose-700">-880 kg (-12.6% vs Expected)</span>
          </div>
        </div>

        {/* Card 3: Stockout Forecasting & Center Runway */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[28px] p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-purple-50 flex items-center justify-center text-purple-700">
                  <Store size={16} />
                </div>
                <div>
                  <h3 className="font-extrabold text-[#10261c] text-sm md:text-base font-display">
                    FPS Depletion Runway
                  </h3>
                  <p className="text-[11px] text-[#7a8b84] font-medium">Estimated days until inventory exhaustion</p>
                </div>
              </div>
              <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-purple-50 text-purple-800 border border-purple-200">
                5 Centers
              </span>
            </div>

            <div className="mt-4 space-y-2.5">
              {[
                { id: 'PWD001', name: 'Shakti FPS', days: 14.2, status: 'Healthy', stock: '1,500 kg' },
                { id: 'PWD002', name: 'Jan Seva Kendra', days: 6.5, status: 'Warning', stock: '1,020 kg' },
                { id: 'PWD003', name: 'Annapurna Store', days: 18.0, status: 'Healthy', stock: '1,900 kg' },
                { id: 'PWD004', name: 'Bharat Point', days: 3.8, status: 'Critical', stock: '650 kg' },
                { id: 'PWD005', name: 'Lok Kalyan FPS', days: 11.5, status: 'Healthy', stock: '1,000 kg' },
              ].map((shop) => (
                <div key={shop.id} className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50/70 border border-slate-200/50 hover:bg-white transition-all text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-slate-500 text-[11px]">{shop.id}</span>
                    <span className="font-semibold text-slate-800">{shop.name}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-slate-500 font-mono text-[11px]">{shop.stock}</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                      shop.status === 'Critical' ? 'bg-rose-100 text-rose-700' :
                      shop.status === 'Warning' ? 'bg-amber-100 text-amber-700' :
                      'bg-emerald-100 text-emerald-800'
                    }`}>
                      {shop.days} days
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Critical Reorder Required:</span>
            <span className="font-bold text-rose-700">PWD004 (&lt; 4 days remaining)</span>
          </div>
        </div>
      </div>
    </div>
  );
};
