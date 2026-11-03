import React, { useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { 
  Truck, 
  Scale, 
  ArrowUpRight, 
  Search, 
  PlusCircle, 
  X, 
  CheckCircle2, 
  Store, 
  FileDown, 
  TrendingUp, 
  Eye, 
  BarChart2,
  AlertTriangle,
  Calendar,
  Layers,
  ChevronDown,
  User,
  ShieldCheck,
  Check
} from 'lucide-react';
import { mockPWDShops, PWDShop } from '../data/mockData';

export const RationDistribution: React.FC = () => {
  const [shops, setShops] = useState<PWDShop[]>(mockPWDShops);
  const [selectedState, setSelectedState] = useState<string>('All');
  const [selectedDistrict, setSelectedDistrict] = useState<string>('All');
  const [selectedStatus, setSelectedStatus] = useState<'All' | 'Healthy' | 'Warning' | 'Critical'>('All');
  const [selectedPeriod, setSelectedPeriod] = useState<string>('2026-10');
  const [searchQuery, setSearchQuery] = useState('');

  // Modals & toast states
  const [isRecordModalOpen, setIsRecordModalOpen] = useState(false);
  const [selectedShop, setSelectedShop] = useState<PWDShop | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Record Distribution Form State
  const [formData, setFormData] = useState({
    district: 'Ghaziabad',
    pwdId: 'PWD001',
    commodity: 'Rice',
    quantityKg: 500,
    vehicleNo: 'UP-14-BT-5421',
    driverName: 'Ramesh Chandra'
  });

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleOpenRecordModal = () => {
    setFormData({
      district: 'Ghaziabad',
      pwdId: 'PWD001',
      commodity: 'Rice',
      quantityKg: 500,
      vehicleNo: 'UP-14-BT-5421',
      driverName: 'Ramesh Chandra'
    });
    setIsRecordModalOpen(true);
  };

  const handleRecordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const qty = Number(formData.quantityKg) || 0;
    if (qty <= 0) return;

    setShops(prev => prev.map(s => {
      if (s.pwd_id === formData.pwdId) {
        return {
          ...s,
          distributed_kg: s.distributed_kg + qty,
          closing_stock_kg: Math.max(0, s.closing_stock_kg - qty)
        };
      }
      return s;
    }));

    setIsRecordModalOpen(false);
    showToast(`Logged consignment distribution of ${qty.toLocaleString()} kg to ${formData.pwdId} (${formData.district})`);
  };

  const handleExportCSV = () => {
    const headers = "PWD ID,Shop Name,District,State,Dealer ID,Capacity (kg),Received (kg),Distributed (kg),Physical Stock (kg),Discrepancy (kg),Inspection Status\n";
    const rows = filteredShops.map(s => 
      `"${s.pwd_id}","${s.shop_name}","${s.district}","${s.state}","${s.dealer_id}",${s.monthly_capacity_kg},${s.received_kg},${s.distributed_kg},${s.physical_stock_kg},${s.discrepancy_kg},"${s.inspection_status}"`
    ).join("\n");
    
    const blob = new Blob([headers + rows], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ration-distribution-${selectedPeriod}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    showToast(`Exported ${filteredShops.length} distribution records as CSV`);
  };

  // Distinct lists for filter dropdowns
  const availableStates = useMemo(() => ['All', ...Array.from(new Set(mockPWDShops.map(s => s.state)))], []);
  const availableDistricts = useMemo(() => {
    const filtered = selectedState === 'All' ? mockPWDShops : mockPWDShops.filter(s => s.state === selectedState);
    return ['All', ...Array.from(new Set(filtered.map(s => s.district)))];
  }, [selectedState]);

  // Filtered Shops
  const filteredShops = useMemo(() => {
    return shops.filter(s => {
      const matchState = selectedState === 'All' || s.state === selectedState;
      const matchDistrict = selectedDistrict === 'All' || s.district === selectedDistrict;
      
      let shopStatus = 'Healthy';
      if (s.inspection_status === 'failed' || s.discrepancy_kg < -100) {
        shopStatus = 'Critical';
      } else if (s.inspection_status === 'pending' || s.discrepancy_kg < 0) {
        shopStatus = 'Warning';
      }

      const matchStatus = selectedStatus === 'All' || shopStatus === selectedStatus;
      const matchSearch = s.shop_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          s.pwd_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          s.district.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          s.dealer_id.toLowerCase().includes(searchQuery.toLowerCase());

      return matchState && matchDistrict && matchStatus && matchSearch;
    });
  }, [shops, selectedState, selectedDistrict, selectedStatus, searchQuery]);

  // Aggregated KPIs
  const totalCapacity = useMemo(() => filteredShops.reduce((acc, s) => acc + s.monthly_capacity_kg, 0), [filteredShops]);
  const totalReceived = useMemo(() => filteredShops.reduce((acc, s) => acc + s.received_kg, 0), [filteredShops]);
  const totalDistributed = useMemo(() => filteredShops.reduce((acc, s) => acc + s.distributed_kg, 0), [filteredShops]);
  const totalPhysical = useMemo(() => filteredShops.reduce((acc, s) => acc + s.physical_stock_kg, 0), [filteredShops]);
  const totalDiscrepancy = useMemo(() => filteredShops.reduce((acc, s) => acc + s.discrepancy_kg, 0), [filteredShops]);

  // District Progress Bars
  const districtStats = useMemo(() => {
    const map: Record<string, { name: string; capacity: number; distributed: number; count: number; status: string }> = {};
    filteredShops.forEach(s => {
      if (!map[s.district]) {
        map[s.district] = { name: s.district, capacity: 0, distributed: 0, count: 0, status: 'Healthy' };
      }
      map[s.district].capacity += s.monthly_capacity_kg;
      map[s.district].distributed += s.distributed_kg;
      map[s.district].count += 1;
      if (s.inspection_status === 'failed') map[s.district].status = 'Critical';
      else if (s.discrepancy_kg < -50 && map[s.district].status !== 'Critical') map[s.district].status = 'Warning';
    });
    return Object.values(map);
  }, [filteredShops]);

  const maxDistrictVolume = Math.max(...districtStats.map(d => d.distributed), 1);

  return (
    <div className="space-y-6 pb-12 animate-fadeIn">
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white/80 backdrop-blur-xl border border-white/80 p-5 rounded-3xl shadow-sm">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl md:text-3xl font-extrabold text-[#10261c] tracking-tight font-display">
              Ration Distribution
            </h1>
            <span className="px-3 py-1 rounded-full text-[11px] font-bold tracking-wide uppercase bg-emerald-50 text-emerald-800 border border-emerald-300">
              October 2026 Dataset Active
            </span>
            <span className="px-2.5 py-1 rounded-full text-[11px] font-mono text-slate-500 bg-slate-100 border border-slate-200">
              Period: {selectedPeriod}
            </span>
          </div>
          <p className="text-xs md:text-sm text-[#5d7468] mt-1 font-medium">
            Live distribution quotas, quantity lifted, physical stock reconciliations, and outlet inspection records.
          </p>
        </div>

        {/* Action Buttons: Record Distribution & Export */}
        <div className="flex items-center gap-2.5 self-start sm:self-center">
          <button
            type="button"
            onClick={handleExportCSV}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full border border-slate-200/80 bg-white hover:bg-slate-50 text-xs md:text-sm font-bold text-[#10261c] shadow-xs transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
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

      {/* 4 Connected KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Allocation Capacity */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Total Allocation</span>
            <div className="w-8 h-8 rounded-full bg-[#14654a]/12 flex items-center justify-center text-[#14654a]">
              <Truck size={17} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              {totalCapacity.toLocaleString()} kg
            </span>
            <span className="text-[11px] font-bold text-[#0d6840] flex items-center gap-0.5">
              Monthly Cap
            </span>
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Across {filteredShops.length} Fair Price Shop centers
          </div>
        </div>

        {/* Card 2: Quantity Lifted / Received */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Quantity Lifted (Inflow)</span>
            <div className="w-8 h-8 rounded-full bg-blue-50 flex items-center justify-center text-blue-700">
              <Layers size={17} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-blue-800 font-display">
              {totalReceived.toLocaleString()} kg
            </span>
            <span className="text-[11px] font-bold text-blue-700">
              FCI Despatch
            </span>
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            Warehouse consignment intake
          </div>
        </div>

        {/* Card 3: Total Reported Distributed */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Reported Distributed</span>
            <div className="w-8 h-8 rounded-full bg-[#2fa56f]/15 flex items-center justify-center text-[#14654a]">
              <ArrowUpRight size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#14654a] font-display">
              {totalDistributed.toLocaleString()} kg
            </span>
            <span className="text-[11px] font-bold text-[#14654a] flex items-center gap-1">
              <TrendingUp size={12} />
              5,600 kg Rice
            </span>
          </div>
          <div className="text-[11px] text-slate-500 mt-1">
            3,850 kg Wheat disbursed
          </div>
        </div>

        {/* Card 4: Audited Stock & Discrepancy */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Physical Verified Stock</span>
            <div className="w-8 h-8 rounded-full bg-rose-50 flex items-center justify-center text-rose-600">
              <Scale size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              {totalPhysical.toLocaleString()} kg
            </span>
            <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 border border-rose-200">
              {totalDiscrepancy} kg Net
            </span>
          </div>
          <div className="text-[11px] text-rose-600 font-semibold mt-1 flex items-center gap-1">
            <AlertTriangle size={12} />
            Discrepancy at PWD002 & PWD004
          </div>
        </div>
      </div>

      {/* Visual Volume Comparison Card */}
      <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[28px] p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart2 size={18} className="text-[#14654a]" />
            <h3 className="font-extrabold text-[#10261c] text-sm md:text-base font-display">
              District Allocation Volume Breakdown (October 2026 Run)
            </h3>
          </div>
          <span className="text-xs text-[#5d7468] font-medium hidden sm:inline">
            Relative quota distribution across Ghaziabad, East Delhi, and Noida
          </span>
        </div>

        <div className="space-y-3 pt-1">
          {districtStats.map(d => {
            const percent = (d.distributed / maxDistrictVolume) * 100;
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
                    <span className="text-[11px] text-[#7a8b84]">({d.count} FPS Outlet{d.count > 1 ? 's' : ''})</span>
                    {d.status === 'Critical' && (
                      <span className="text-[10px] font-bold text-rose-700 bg-rose-50 px-2 py-0.2 rounded border border-rose-200">
                        Failed Inspection
                      </span>
                    )}
                    {d.status === 'Warning' && (
                      <span className="text-[10px] font-bold text-amber-700 bg-amber-50 px-2 py-0.2 rounded border border-amber-200">
                        -280kg Shortage
                      </span>
                    )}
                  </span>
                  <span className="font-mono font-bold text-[#10261c]">
                    {d.distributed.toLocaleString()} kg / {d.capacity.toLocaleString()} kg cap
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

      {/* Comprehensive Filter Toolbar */}
      <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-4 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Dropdowns: State & District */}
        <div className="flex flex-wrap items-center gap-2">
          {/* State */}
          <div className="flex items-center gap-1.5 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5">
            <span className="font-bold text-slate-500">State:</span>
            <select
              value={selectedState}
              onChange={(e) => { setSelectedState(e.target.value); setSelectedDistrict('All'); }}
              className="bg-transparent font-bold text-slate-800 outline-none cursor-pointer"
            >
              {availableStates.map(st => (
                <option key={st} value={st}>{st}</option>
              ))}
            </select>
          </div>

          {/* District */}
          <div className="flex items-center gap-1.5 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5">
            <span className="font-bold text-slate-500">District:</span>
            <select
              value={selectedDistrict}
              onChange={(e) => setSelectedDistrict(e.target.value)}
              className="bg-transparent font-bold text-slate-800 outline-none cursor-pointer"
            >
              {availableDistricts.map(dt => (
                <option key={dt} value={dt}>{dt}</option>
              ))}
            </select>
          </div>

          {/* Reporting Period */}
          <div className="flex items-center gap-1.5 text-xs text-slate-600 bg-emerald-50/70 border border-emerald-200 rounded-xl px-3 py-1.5">
            <Calendar size={13} className="text-emerald-700" />
            <span className="font-bold text-slate-500">Period:</span>
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
              className="bg-transparent font-bold text-emerald-800 outline-none cursor-pointer"
            >
              <option value="2026-10">2026-10 (October Dataset)</option>
              <option value="2026-09">2026-09 (September Archive)</option>
              <option value="2026-08">2026-08 (August Archive)</option>
            </select>
          </div>
        </div>

        {/* Status Filter Pills & Search */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-2xl">
            {(['All', 'Healthy', 'Warning', 'Critical'] as const).map((s) => {
              const isActive = selectedStatus === s;
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => setSelectedStatus(s)}
                  className={`px-3 py-1 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    isActive 
                      ? 'bg-white text-slate-900 shadow-xs' 
                      : 'text-slate-500 hover:text-slate-800'
                  }`}
                >
                  {s}
                </button>
              );
            })}
          </div>

          {/* Search Box */}
          <div className="relative flex-1 sm:w-60">
            <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search shop, dealer, ID..."
              className="w-full pl-9 pr-3.5 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:border-emerald-600 focus:bg-white outline-none"
            />
          </div>
        </div>
      </div>

      {/* Main Fair Price Shop Ledger Table */}
      <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[28px] p-5 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div>
            <h3 className="font-extrabold text-[#10261c] text-sm md:text-base font-display">
              Fair Price Shop Distribution & Inventory Ledger
            </h3>
            <p className="text-xs text-[#5d7468]">
              Showing {filteredShops.length} distribution outlets with recorded grain movements and audit compliance.
            </p>
          </div>
          <span className="text-xs font-mono font-bold text-emerald-800 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
            Official Run 2026-10
          </span>
        </div>

        {filteredShops.length === 0 ? (
          <div className="py-16 text-center">
            <Store size={36} className="mx-auto text-slate-300 mb-2" />
            <h4 className="text-sm font-bold text-slate-700">No matching distribution records found</h4>
            <p className="text-xs text-slate-500 mt-1">Try resetting the district or status filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">
                  <th className="py-3 px-3">Shop ID & Name</th>
                  <th className="py-3 px-3">District & State</th>
                  <th className="py-3 px-3 text-right">Capacity (kg)</th>
                  <th className="py-3 px-3 text-right">Received (kg)</th>
                  <th className="py-3 px-3 text-right">Distributed (kg)</th>
                  <th className="py-3 px-3 text-right">Physical Stock (kg)</th>
                  <th className="py-3 px-3 text-right">Discrepancy</th>
                  <th className="py-3 px-3 text-center">Inspection</th>
                  <th className="py-3 px-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredShops.map(shop => {
                  const hasDeficit = shop.discrepancy_kg < -50;
                  const isFailed = shop.inspection_status === 'failed';

                  return (
                    <tr 
                      key={shop.pwd_id}
                      className="hover:bg-slate-50/80 transition-colors group"
                    >
                      <td className="py-3.5 px-3">
                        <div className="flex items-center gap-2.5">
                          <div className={`w-8 h-8 rounded-xl flex items-center justify-center font-mono font-bold text-[11px] shrink-0 ${
                            isFailed 
                              ? 'bg-rose-50 text-rose-700 border border-rose-200' 
                              : hasDeficit 
                              ? 'bg-amber-50 text-amber-700 border border-amber-200' 
                              : 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                          }`}>
                            {shop.pwd_id}
                          </div>
                          <div>
                            <span className="font-bold text-[#10261c] group-hover:text-emerald-900 block">
                              {shop.shop_name}
                            </span>
                            <span className="text-[11px] text-slate-500 font-mono">
                              Dealer: {shop.dealer_id}
                            </span>
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-3">
                        <span className="font-medium text-slate-800 block">{shop.district}</span>
                        <span className="text-[11px] text-slate-500">{shop.state}</span>
                      </td>

                      <td className="py-3.5 px-3 text-right font-mono font-medium text-slate-700">
                        {shop.monthly_capacity_kg.toLocaleString()} kg
                      </td>

                      <td className="py-3.5 px-3 text-right font-mono font-bold text-blue-700">
                        +{shop.received_kg.toLocaleString()} kg
                      </td>

                      <td className="py-3.5 px-3 text-right font-mono font-bold text-[#10261c]">
                        {shop.distributed_kg.toLocaleString()} kg
                      </td>

                      <td className="py-3.5 px-3 text-right font-mono font-bold text-slate-900">
                        {shop.physical_stock_kg.toLocaleString()} kg
                      </td>

                      <td className="py-3.5 px-3 text-right">
                        {shop.discrepancy_kg < 0 ? (
                          <span className="inline-flex items-center gap-1 font-mono font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                            {shop.discrepancy_kg} kg
                          </span>
                        ) : (
                          <span className="font-mono text-emerald-700 font-semibold">
                            Balanced
                          </span>
                        )}
                      </td>

                      <td className="py-3.5 px-3 text-center">
                        <span className={`inline-block px-2.5 py-0.5 rounded-full text-[10.5px] font-bold uppercase tracking-wider ${
                          shop.inspection_status === 'passed'
                            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                            : shop.inspection_status === 'failed'
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : 'bg-amber-50 text-amber-800 border border-amber-200'
                        }`}>
                          {shop.inspection_status}
                        </span>
                      </td>

                      <td className="py-3.5 px-3 text-center">
                        <button
                          type="button"
                          onClick={() => setSelectedShop(shop)}
                          className="px-3 py-1.5 rounded-lg text-xs font-bold text-slate-700 hover:text-emerald-800 bg-slate-100 hover:bg-slate-200 transition-all inline-flex items-center gap-1 cursor-pointer"
                        >
                          <Eye size={13} />
                          <span>Inspect</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Inspect Shop Detail Modal */}
      {selectedShop && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-md animate-fadeIn">
          <div className="bg-white rounded-3xl shadow-2xl border border-slate-200 max-w-lg w-full overflow-hidden animate-scaleUp">
            <div className="p-6 bg-gradient-to-r from-[#062d22] to-[#14654a] text-white flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20">
                  <Store size={20} className="text-[#7fd8aa]" />
                </div>
                <div>
                  <h3 className="text-base font-bold">{selectedShop.shop_name}</h3>
                  <p className="text-xs text-emerald-200 font-mono">ID: {selectedShop.pwd_id} • Dealer: {selectedShop.dealer_id}</p>
                </div>
              </div>
              <button 
                onClick={() => setSelectedShop(null)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-slate-50 rounded-2xl border border-slate-200">
                  <span className="text-[10px] uppercase font-bold text-slate-500 block">District & State</span>
                  <span className="font-bold text-slate-900 mt-0.5 block">{selectedShop.district}, {selectedShop.state}</span>
                  <span className="text-[10px] text-slate-500 font-mono">GPS: {selectedShop.gps_lat}, {selectedShop.gps_lon}</span>
                </div>

                <div className="p-3 bg-slate-50 rounded-2xl border border-slate-200">
                  <span className="text-[10px] uppercase font-bold text-slate-500 block">Inspection Audit</span>
                  <span className={`font-bold mt-0.5 block uppercase ${
                    selectedShop.inspection_status === 'passed' ? 'text-emerald-700' : 'text-rose-700'
                  }`}>
                    {selectedShop.inspection_status}
                  </span>
                  <span className="text-[10px] text-slate-500">{selectedShop.complaints_count} Citizen Complaints</span>
                </div>
              </div>

              {/* Stock Movement Details */}
              <div className="p-4 rounded-2xl border border-slate-200 bg-slate-50/50 space-y-2 text-xs">
                <div className="font-bold text-slate-800 pb-1 border-b border-slate-200">
                  October 2026 Grain Stock Movement
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Opening Stock:</span>
                  <span className="font-mono font-bold text-slate-800">{selectedShop.opening_stock_kg} kg</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Consignment Received:</span>
                  <span className="font-mono font-bold text-blue-700">+{selectedShop.received_kg} kg</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Reported Distributed:</span>
                  <span className="font-mono font-bold text-slate-800">-{selectedShop.distributed_kg} kg</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Expected Closing:</span>
                  <span className="font-mono font-bold text-slate-800">{selectedShop.closing_stock_kg} kg</span>
                </div>
                <div className="flex justify-between pt-1 border-t border-slate-200">
                  <span className="font-bold text-slate-700">Physically Audited Stock:</span>
                  <span className="font-mono font-bold text-slate-900">{selectedShop.physical_stock_kg} kg</span>
                </div>
                {selectedShop.discrepancy_kg < 0 && (
                  <div className="flex justify-between text-rose-700 font-bold pt-1">
                    <span>Unexplained Stock Deficit:</span>
                    <span className="font-mono">{selectedShop.discrepancy_kg} kg</span>
                  </div>
                )}
              </div>

              {/* Administrative Compliance Notes */}
              <div className="p-3 bg-amber-50 rounded-2xl border border-amber-200 text-amber-900 text-xs space-y-1">
                <span className="font-bold block">Operational Indicators:</span>
                <p>• Late opening days recorded: <strong>{selectedShop.late_opening_days}</strong></p>
                <p>• Manual overrides authorized: <strong>{selectedShop.manual_override_count}</strong></p>
                {selectedShop.inspection_status === 'failed' && (
                  <p className="text-rose-700 font-bold mt-1">⚠️ Out-of-spec compliance: Formal audit enquiry active.</p>
                )}
              </div>
            </div>

            <div className="p-5 bg-slate-50 border-t border-slate-100 flex items-center justify-end">
              <button
                type="button"
                onClick={() => setSelectedShop(null)}
                className="px-5 py-2 rounded-xl text-xs font-bold text-slate-700 hover:bg-slate-200 transition-all cursor-pointer"
              >
                Close Dossier
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Record Distribution Consignment Modal (Redesigned) */}
      {isRecordModalOpen && createPortal(
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setIsRecordModalOpen(false)}
        >
          <div 
            className="bg-white border border-slate-200/80 rounded-[28px] shadow-[0_25px_60px_-15px_rgba(0,0,0,0.3)] w-full max-w-lg overflow-hidden flex flex-col animate-in zoom-in-95 duration-200 max-h-[92vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="relative px-6 pt-5 pb-4 border-b border-slate-100 bg-gradient-to-r from-emerald-50/70 via-teal-50/30 to-slate-50/50">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3.5">
                  <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-[#14654a] to-[#0a3829] text-white flex items-center justify-center shadow-lg shadow-[#14654a]/25 shrink-0 ring-4 ring-emerald-500/10">
                    <Truck size={20} className="stroke-[2.2]" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-extrabold text-[#10261c] text-lg leading-tight font-display tracking-tight">
                        Record Consignment Dispatch
                      </h3>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase bg-[#14654a]/10 text-[#14654a] border border-[#14654a]/20">
                        Outbound Dispatch
                      </span>
                    </div>
                    <p className="text-xs text-[#5d7468] mt-0.5">
                      Generate transit challan and allocate warehouse quota to Fair Price Shop
                    </p>
                  </div>
                </div>
                <button 
                  type="button"
                  onClick={() => setIsRecordModalOpen(false)} 
                  className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-white/80 border border-transparent hover:border-slate-200 transition-all shadow-none hover:shadow-sm"
                  aria-label="Close dialog"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleRecordSubmit} className="p-6 overflow-y-auto space-y-4 text-xs md:text-sm custom-scrollbar">
              {/* Destination Fair Price Shop */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-700">
                    Destination Fair Price Shop <span className="text-rose-500">*</span>
                  </label>
                  <span className="text-[10.5px] font-medium text-slate-400">Target Distribution Center</span>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Store size={16} />
                  </div>
                  <select
                    value={formData.pwdId}
                    onChange={(e) => {
                      const shop = shops.find(s => s.pwd_id === e.target.value);
                      setFormData({
                        ...formData,
                        pwdId: e.target.value,
                        district: shop?.district || 'Ghaziabad'
                      });
                    }}
                    className="w-full pl-10 pr-9 py-2.5 bg-slate-50/80 hover:bg-slate-50 focus:bg-white border border-slate-200/90 rounded-xl text-xs sm:text-sm font-semibold text-slate-800 focus:outline-none focus:border-[#14654a] focus:ring-2 focus:ring-[#14654a]/15 transition-all appearance-none cursor-pointer shadow-sm"
                  >
                    {shops.map(s => (
                      <option key={s.pwd_id} value={s.pwd_id}>
                        {s.pwd_id} — {s.shop_name} ({s.district})
                      </option>
                    ))}
                  </select>
                  <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-slate-400">
                    <ChevronDown size={15} />
                  </div>
                </div>

                {/* Target Shop Context Badge */}
                {(() => {
                  const targetShop = shops.find(s => s.pwd_id === formData.pwdId);
                  if (!targetShop) return null;
                  return (
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200/60 text-[11px] text-slate-600">
                      <span className="font-semibold text-slate-700">{targetShop.district}</span>
                      <span className="text-slate-300">•</span>
                      <span>Stock: <strong className="text-slate-800">{targetShop.closing_stock_kg.toLocaleString()} kg</strong></span>
                      <span className="text-slate-300">•</span>
                      <span>Dealer: <span className="font-mono font-bold text-slate-700">{targetShop.dealer_id}</span></span>
                    </div>
                  );
                })()}
              </div>

              {/* Commodity Category Cards */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-700">Commodity Type</label>
                  <span className="text-[10.5px] font-medium text-slate-400">Ration Grain Grade</span>
                </div>
                <div className="grid grid-cols-2 gap-2.5">
                  {[
                    { id: 'Rice', label: 'Rice (Grade A)', desc: 'Standard PDS distribution lot' },
                    { id: 'Wheat', label: 'Wheat (Milling)', desc: 'Whole grain wheat quota' }
                  ].map(com => {
                    const isSelected = formData.commodity === com.id;
                    return (
                      <button
                        key={com.id}
                        type="button"
                        onClick={() => setFormData({ ...formData, commodity: com.id })}
                        className={`p-3 rounded-xl border text-left transition-all relative ${
                          isSelected 
                            ? 'bg-emerald-50/70 border-[#14654a] shadow-sm shadow-emerald-900/5 ring-1 ring-[#14654a]' 
                            : 'bg-white hover:bg-slate-50/80 border-slate-200/80'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-0.5">
                          <span className={`text-xs font-extrabold ${isSelected ? 'text-[#14654a]' : 'text-slate-800'}`}>
                            {com.label}
                          </span>
                          {isSelected && <Check size={13} className="text-[#14654a] stroke-[3]" />}
                        </div>
                        <p className="text-[10.5px] font-medium text-slate-500 leading-tight">{com.desc}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Quantity (kg) with quick increments */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-slate-700">
                    Dispatch Quantity <span className="text-rose-500">*</span>
                  </label>
                  <div className="flex items-center gap-1">
                    {[100, 250, 500].map(addAmount => (
                      <button
                        key={addAmount}
                        type="button"
                        onClick={() => setFormData(prev => ({ ...prev, quantityKg: prev.quantityKg + addAmount }))}
                        className="px-2 py-0.5 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-[10px] transition-colors"
                        title={`Add ${addAmount} kg`}
                      >
                        +{addAmount}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                    <Scale size={16} />
                  </div>
                  <input
                    type="number"
                    min="1"
                    required
                    value={formData.quantityKg}
                    onChange={(e) => setFormData({ ...formData, quantityKg: Number(e.target.value) })}
                    className="w-full pl-10 pr-14 py-2.5 bg-slate-50/80 hover:bg-slate-50 focus:bg-white border border-slate-200/90 rounded-xl text-sm font-mono font-bold text-slate-800 focus:outline-none focus:border-[#14654a] focus:ring-2 focus:ring-[#14654a]/15 transition-all shadow-sm"
                  />
                  <div className="absolute inset-y-0 right-0 pr-3.5 flex items-center pointer-events-none text-xs font-bold text-slate-500">
                    KG
                  </div>
                </div>
              </div>

              {/* 2-Column Row: Vehicle Challan & Driver */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {/* Vehicle Challan No. */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-700">Vehicle Challan No.</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <Truck size={15} />
                    </div>
                    <input
                      type="text"
                      placeholder="e.g. UP-14-BT-5421"
                      value={formData.vehicleNo}
                      onChange={(e) => setFormData({ ...formData, vehicleNo: e.target.value })}
                      className="w-full pl-9 pr-3.5 py-2.5 bg-slate-50/80 hover:bg-slate-50 focus:bg-white border border-slate-200/90 rounded-xl text-xs font-mono font-bold text-slate-800 uppercase focus:outline-none focus:border-[#14654a] focus:ring-2 focus:ring-[#14654a]/15 transition-all shadow-sm"
                    />
                  </div>
                </div>

                {/* Authorized Driver */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-700">Authorized Driver</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                      <User size={15} />
                    </div>
                    <input
                      type="text"
                      placeholder="e.g. Ramesh Chandra"
                      value={formData.driverName}
                      onChange={(e) => setFormData({ ...formData, driverName: e.target.value })}
                      className="w-full pl-9 pr-3.5 py-2.5 bg-slate-50/80 hover:bg-slate-50 focus:bg-white border border-slate-200/90 rounded-xl text-xs font-semibold text-slate-800 focus:outline-none focus:border-[#14654a] focus:ring-2 focus:ring-[#14654a]/15 transition-all shadow-sm"
                    />
                  </div>
                </div>
              </div>

              {/* Action Buttons & Ledger Notice */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-slate-100">
                <div className="flex items-center gap-1.5 text-slate-500 text-[11px]">
                  <ShieldCheck size={14} className="text-[#14654a] shrink-0" />
                  <span>Transit logged in State PDS Register</span>
                </div>
                <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                  <button
                    type="button"
                    onClick={() => setIsRecordModalOpen(false)}
                    className="flex-1 sm:flex-initial px-4 py-2.5 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50 hover:text-slate-800 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 sm:flex-initial px-5 py-2.5 rounded-xl text-white text-xs font-bold shadow-md transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center gap-2"
                    style={{
                      background: 'linear-gradient(135deg, #062d22, #14654a 52%, #2fa56f)',
                      boxShadow: '0 8px 18px -4px rgba(20, 101, 74, 0.45)'
                    }}
                  >
                    <CheckCircle2 size={14} />
                    <span>Confirm Distribution</span>
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};
