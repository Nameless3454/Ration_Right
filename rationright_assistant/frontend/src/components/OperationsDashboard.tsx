import React, { useState } from "react";
import {
  Users,
  Package,
  AlertTriangle,
  Store,
  CheckCircle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Scale,
  RefreshCw,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { SnapshotMetricsResponse } from "../types/api";

interface OperationsDashboardProps {
  metrics: SnapshotMetricsResponse | null;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  onAskQuestion: (question: string) => void;
}

export const OperationsDashboard: React.FC<OperationsDashboardProps> = ({
  metrics,
  isLoading,
  error,
  onRefresh,
  onAskQuestion,
}) => {
  const [activeTab, setActiveTab] = useState<"overview" | "inventory" | "shops">("overview");
  const [inventoryCommodityFilter, setInventoryCommodityFilter] = useState<string>("ALL");

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] text-slate-500 space-y-3">
        <RefreshCw className="w-8 h-8 animate-spin text-gov-600" />
        <p className="text-sm font-medium">Loading weekly operations metrics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-xl my-6 max-w-4xl mx-auto text-center space-y-3">
        <AlertTriangle className="w-10 h-10 text-red-500 mx-auto" />
        <h3 className="text-base font-bold text-red-900">Unable to load metrics</h3>
        <p className="text-xs text-red-700">{error}</p>
        <button
          onClick={onRefresh}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Retry
        </button>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="text-center py-16 text-slate-500">
        <Package className="w-12 h-12 text-slate-400 mx-auto mb-3" />
        <p className="text-sm">No dataset metrics available. Import a batch to get started.</p>
      </div>
    );
  }

  const { beneficiaries, inventory, audits, shop_complaints, transactions } = metrics;

  // Filtered inventory
  const filteredInventory = inventory.filter((item) => {
    if (inventoryCommodityFilter === "ALL") return true;
    return item.commodity.toUpperCase() === inventoryCommodityFilter.toUpperCase();
  });

  // Aggregated commodity metrics for Recharts
  const chartData = [
    {
      commodity: "Rice",
      Received: inventory
        .filter((i) => i.commodity === "Rice")
        .reduce((acc, curr) => acc + curr.received_kg, 0),
      Distributed: inventory
        .filter((i) => i.commodity === "Rice")
        .reduce((acc, curr) => acc + curr.distributed_kg, 0),
      Closing: inventory
        .filter((i) => i.commodity === "Rice")
        .reduce((acc, curr) => acc + curr.closing_stock_kg, 0),
      Physical: inventory
        .filter((i) => i.commodity === "Rice")
        .reduce((acc, curr) => acc + curr.physical_stock_kg, 0),
    },
    {
      commodity: "Wheat",
      Received: inventory
        .filter((i) => i.commodity === "Wheat")
        .reduce((acc, curr) => acc + curr.received_kg, 0),
      Distributed: inventory
        .filter((i) => i.commodity === "Wheat")
        .reduce((acc, curr) => acc + curr.distributed_kg, 0),
      Closing: inventory
        .filter((i) => i.commodity === "Wheat")
        .reduce((acc, curr) => acc + curr.closing_stock_kg, 0),
      Physical: inventory
        .filter((i) => i.commodity === "Wheat")
        .reduce((acc, curr) => acc + curr.physical_stock_kg, 0),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Snapshot Summary Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-gov-700 tracking-wide uppercase">
              Current Weekly Snapshot
            </span>
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-gov-100 text-gov-800 border border-gov-200">
              {metrics.dataset_name}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Import ID: <span className="font-mono text-slate-700">{metrics.import_id}</span> • Timestamp:{" "}
            {new Date(metrics.import_timestamp).toLocaleString()}
          </p>
        </div>

        {/* View Tabs */}
        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg self-start sm:self-auto">
          <button
            onClick={() => setActiveTab("overview")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
              activeTab === "overview"
                ? "bg-white text-gov-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab("inventory")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
              activeTab === "inventory"
                ? "bg-white text-gov-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Inventory ({inventory.length})
          </button>
          <button
            onClick={() => setActiveTab("shops")}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
              activeTab === "shops"
                ? "bg-white text-gov-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            FPS Compliance ({shop_complaints.length})
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Beneficiaries Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Beneficiaries
            </span>
            <div className="p-2 rounded-lg bg-blue-50 text-gov-700">
              <Users className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {beneficiaries.total_beneficiaries.toLocaleString()}
            </span>
            <span className="text-xs text-slate-500">enrolled</span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <span>PHH: <strong className="text-slate-800">{beneficiaries.phh_count}</strong></span>
            <span>AAY: <strong className="text-slate-800">{beneficiaries.aay_count}</strong></span>
            <span className="text-emerald-600">Verified: <strong>{beneficiaries.verified_count}</strong></span>
          </div>
        </div>

        {/* Flagged Review Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              System Review Leads
            </span>
            <div className="p-2 rounded-lg bg-amber-50 text-amber-600">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-amber-700">
              {beneficiaries.duplicate_flag_count + beneficiaries.multiple_claims_count}
            </span>
            <span className="text-xs text-slate-500">review flags</span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <button
              onClick={() => onAskQuestion("Which records have duplicate flags?")}
              className="text-amber-700 hover:underline"
            >
              Duplicates: <strong>{beneficiaries.duplicate_flag_count}</strong>
            </button>
            <button
              onClick={() => onAskQuestion("Which beneficiaries are flagged for multiple claims?")}
              className="text-amber-700 hover:underline"
            >
              Multiple Claims: <strong>{beneficiaries.multiple_claims_count}</strong>
            </button>
          </div>
        </div>

        {/* Distributed Foodgrains Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Distributed
            </span>
            <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
              <Scale className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {(transactions.total_grain_distributed_kg || transactions.total_distributed_kg || 0).toLocaleString()}
            </span>
            <span className="text-xs text-slate-500">kg foodgrains</span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <span>Txns: <strong>{transactions.total_transactions}</strong></span>
            <span>Biometric: <strong className="text-emerald-700">{transactions.biometric_count}</strong></span>
            <span>Overrides: <strong className="text-amber-600">{transactions.manual_override_count}</strong></span>
          </div>
        </div>

        {/* FPS Compliance Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow-md transition">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Fair Price Shops
            </span>
            <div className="p-2 rounded-lg bg-indigo-50 text-indigo-600">
              <Store className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">
              {audits.total_audits}
            </span>
            <span className="text-xs text-slate-500">monitored shops</span>
          </div>
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600">
            <span>Complaints: <strong className="text-red-600">{audits.total_complaints}</strong></span>
            <span>Failed: <strong className="text-red-700">{audits.failed_inspections}</strong></span>
            <span>Late Days: <strong>{audits.late_openings_total}</strong></span>
          </div>
        </div>
      </div>

      {/* Main Content Area based on Active Tab */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Commodity Stock Chart */}
          <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h4 className="text-sm font-bold text-slate-900">Commodity Stock Movement (Kg)</h4>
                <p className="text-xs text-slate-500">Received, Distributed & Closing Balances</p>
              </div>
              <button
                onClick={() => onAskQuestion("What is the current stock of rice and wheat?")}
                className="text-xs text-gov-700 font-semibold hover:underline"
              >
                Ask Assistant →
              </button>
            </div>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="commodity" stroke="#64748b" fontSize={12} />
                  <YAxis stroke="#64748b" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1e293b",
                      borderRadius: "8px",
                      color: "#fff",
                      fontSize: "12px",
                      border: "none",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px" }} />
                  <Bar dataKey="Received" fill="#3c82b5" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Distributed" fill="#138808" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Closing" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Physical" fill="#64748b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Citizen Complaints Ranking */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-bold text-slate-900">Highest Complaints FPS</h4>
                <button
                  onClick={() => onAskQuestion("Which shop has the highest complaints?")}
                  className="text-xs text-gov-700 font-semibold hover:underline"
                >
                  Full Report →
                </button>
              </div>
              <p className="text-xs text-slate-500 mb-3">
                Shops requiring departmental review based on citizen feedback
              </p>

              <div className="space-y-2.5">
                {shop_complaints.slice(0, 4).map((shop, idx) => (
                  <div
                    key={shop.pwd_id}
                    className="p-2.5 rounded-lg border border-slate-100 bg-slate-50/70 hover:bg-slate-50 transition flex items-center justify-between text-xs"
                  >
                    <div>
                      <p className="font-semibold text-slate-800">{shop.shop_name}</p>
                      <p className="text-[11px] text-slate-500 font-mono">
                        {shop.pwd_id} • {shop.district}
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="inline-block px-2 py-0.5 rounded-full font-bold bg-red-100 text-red-700 text-[11px]">
                        {shop.complaints_count} complaints
                      </span>
                      <p className="text-[10px] text-slate-500 mt-0.5">
                        Status: <span className="font-semibold">{shop.inspection_status}</span>
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500 italic">
              Notice: Complaints are operational indicators for field inquiry, not proof of wrongdoing.
            </div>
          </div>
        </div>
      )}

      {/* Inventory Ledger Tab */}
      {activeTab === "inventory" && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-bold text-slate-900">Commodity Inventory & Physical Audit Ledger</h4>
              <p className="text-xs text-slate-500">
                Book closing stock versus actual ground physical audit verification
              </p>
            </div>
            {/* Commodity Filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-500 font-medium">Commodity:</span>
              <select
                value={inventoryCommodityFilter}
                onChange={(e) => setInventoryCommodityFilter(e.target.value)}
                className="text-xs border border-slate-300 rounded-md px-2 py-1 bg-white font-medium"
              >
                <option value="ALL">All Commodities</option>
                <option value="RICE">Rice Only</option>
                <option value="WHEAT">Wheat Only</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-xs text-left">
              <thead className="bg-slate-50 border-y border-slate-200 text-slate-700 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-2.5 px-3">Fair Price Shop</th>
                  <th className="py-2.5 px-3">Commodity</th>
                  <th className="py-2.5 px-3 text-right">Opening (kg)</th>
                  <th className="py-2.5 px-3 text-right">Received (kg)</th>
                  <th className="py-2.5 px-3 text-right">Distributed (kg)</th>
                  <th className="py-2.5 px-3 text-right">Book Closing</th>
                  <th className="py-2.5 px-3 text-right">Physical Audit</th>
                  <th className="py-2.5 px-3 text-right">Discrepancy</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredInventory.map((item) => {
                  const discrepancy = item.physical_discrepancy_kg;
                  const isShortage = discrepancy < 0;
                  const isSurplus = discrepancy > 0;

                  return (
                    <tr key={item.inventory_id} className="hover:bg-slate-50/70 transition">
                      <td className="py-2.5 px-3">
                        <span className="font-semibold text-slate-900">{item.shop_name}</span>
                        <span className="block font-mono text-[10px] text-slate-400">{item.pwd_id}</span>
                      </td>
                      <td className="py-2.5 px-3 font-medium">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                            item.commodity === "Rice"
                              ? "bg-amber-50 text-amber-800 border border-amber-200"
                              : "bg-orange-50 text-orange-800 border border-orange-200"
                          }`}
                        >
                          {item.commodity}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono">{item.opening_stock_kg.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-right font-mono text-gov-700">+{item.received_kg.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-right font-mono text-emerald-700">-{item.distributed_kg.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-right font-mono font-semibold">{item.closing_stock_kg.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-right font-mono font-semibold">{item.physical_stock_kg.toLocaleString()}</td>
                      <td className="py-2.5 px-3 text-right">
                        <span
                          className={`inline-block px-2 py-0.5 rounded font-mono font-bold text-[11px] ${
                            isShortage
                              ? "bg-red-100 text-red-800"
                              : isSurplus
                              ? "bg-blue-100 text-blue-800"
                              : "bg-emerald-100 text-emerald-800"
                          }`}
                        >
                          {discrepancy > 0 ? `+${discrepancy}` : discrepancy} kg
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* FPS Compliance Tab */}
      {activeTab === "shops" && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-bold text-slate-900">Fair Price Shops Operational Audit Ledger</h4>
              <p className="text-xs text-slate-500">Citizen complaints, inspection status, and manual overrides</p>
            </div>
            <button
              onClick={() => onAskQuestion("Give me a summary of shop audits")}
              className="text-xs text-gov-700 font-semibold hover:underline"
            >
              Ask AI Summary →
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-xs text-left">
              <thead className="bg-slate-50 border-y border-slate-200 text-slate-700 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-2.5 px-3">Shop ID & Name</th>
                  <th className="py-2.5 px-3">District, State</th>
                  <th className="py-2.5 px-3 text-center">Citizen Complaints</th>
                  <th className="py-2.5 px-3 text-center">Inspection Status</th>
                  <th className="py-2.5 px-3 text-center">Late Opening Days</th>
                  <th className="py-2.5 px-3 text-center">Manual Overrides</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shop_complaints.map((shop) => (
                  <tr key={shop.pwd_id} className="hover:bg-slate-50/70 transition">
                    <td className="py-2.5 px-3">
                      <span className="font-semibold text-slate-900">{shop.shop_name}</span>
                      <span className="block font-mono text-[10px] text-slate-400">{shop.pwd_id}</span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">
                      {shop.district}, {shop.state}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full font-bold text-[11px] ${
                          shop.complaints_count > 3
                            ? "bg-red-100 text-red-800"
                            : shop.complaints_count > 0
                            ? "bg-amber-100 text-amber-800"
                            : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        {shop.complaints_count}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                          shop.inspection_status === "PASSED"
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-red-100 text-red-800"
                        }`}
                      >
                        {shop.inspection_status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center font-mono">{shop.late_opening_days} days</td>
                    <td className="py-2.5 px-3 text-center font-mono">{shop.manual_override_count}</td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => onAskQuestion(`What is the operational profile of shop ${shop.pwd_id}?`)}
                        className="text-xs text-gov-700 hover:text-gov-900 font-semibold underline"
                      >
                        Inquire
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

