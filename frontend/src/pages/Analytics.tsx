import React from 'react';
import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export const Analytics: React.FC = () => {
  const data = [
    { date: 'Aug 1', availableInventory: 95000, stockWithdrawn: 14500 },
    { date: 'Aug 2', availableInventory: 80500, stockWithdrawn: 16210 },
    { date: 'Aug 3', availableInventory: 64290, stockWithdrawn: 13890 },
    { date: 'Aug 4', availableInventory: 50400, stockWithdrawn: 17765 },
    { date: 'Aug 5', availableInventory: 32635, stockWithdrawn: 18980 },
    { date: 'Aug 6', availableInventory: 110000, stockWithdrawn: 15420 }, // stock replenished
    { date: 'Aug 7', availableInventory: 94580, stockWithdrawn: 16900 }
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">Analytics Dashboard</h1>
        <p className="text-xs md:text-sm text-slate-500 mt-1">Transaction analytics, available stocks, and beneficiary withdrawal logs.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-5">
        <h3 className="font-bold text-slate-800 text-sm md:text-base mb-4">Stock Withdrawal vs. Available Inventory</h3>
        <p className="text-xs text-slate-400 mb-4">Visualizes available reserve inventory levels (Line, left axis) against daily quantities taken by beneficiaries (Bar, right axis).</p>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="date" stroke="#94A3B8" fontSize={11} />
              {/* Left Y-Axis for Available Inventory */}
              <YAxis yAxisId="left" stroke="#0284C7" fontSize={11} label={{ value: 'Available Inventory (kg)', angle: -90, position: 'insideLeft', offset: -5, style: { textAnchor: 'middle', fill: '#0284C7', fontSize: 11, fontWeight: 'bold' } }} />
              {/* Right Y-Axis for Stock Withdrawn */}
              <YAxis yAxisId="right" orientation="right" stroke="#0D9488" fontSize={11} label={{ value: 'Stock Taken by Beneficiaries (kg)', angle: 90, position: 'insideRight', offset: 10, style: { textAnchor: 'middle', fill: '#0D9488', fontSize: 11, fontWeight: 'bold' } }} />
              <Tooltip formatter={(value) => `${Number(value).toLocaleString()} kg`} />
              <Legend wrapperStyle={{ fontSize: 11, fontWeight: '600', color: '#475569' }} />
              {/* Bar showing Stock Taken */}
              <Bar yAxisId="right" dataKey="stockWithdrawn" name="Stock Taken by Beneficiaries" fill="#99F6E4" stroke="#0D9488" strokeWidth={2} radius={[4, 4, 0, 0]} barSize={36} />
              {/* Line showing Available Inventory */}
              <Line yAxisId="left" type="monotone" dataKey="availableInventory" name="Available Inventory" stroke="#0284C7" strokeWidth={2.5} dot={{ r: 4 }} activeDot={{ r: 6 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
