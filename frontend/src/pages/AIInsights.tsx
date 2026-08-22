import React from 'react';
import { Sparkles, BrainCircuit } from 'lucide-react';

export const AIInsights: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">AI Insights</h1>
        <p className="text-xs md:text-sm text-slate-500 mt-1">Intelligent insights surfaced by RationRight agents.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col gap-4">
        <div className="flex gap-4 items-start bg-sky-50/20 border border-sky-100 p-4 rounded-lg">
          <Sparkles className="text-[#0284C7] mt-1 shrink-0" size={20} />
          <div>
            <h4 className="font-bold text-slate-800 text-sm">Systemic Timing Anomalies detected in East Delhi</h4>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              Agent 3 compiles timing statistics across FPS terminals in East Delhi. Multiple terminals recorded successful biometric check-ins spaced under 30 seconds apart, implying synthetic card activity or manual logging bypasses.
            </p>
          </div>
        </div>

        <div className="flex gap-4 items-start bg-slate-50 border border-slate-100 p-4 rounded-lg">
          <BrainCircuit className="text-slate-500 mt-1 shrink-0" size={20} />
          <div>
            <h4 className="font-bold text-slate-800 text-sm">Decline in Active Beneficiary Logins (Gwalior)</h4>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              Inventory audits reveal steady commodity withdrawals despite a 14% drop in unique Aadhaar verified beneficiary logins. Recommended for administrative auditing.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
