import React from 'react';
import { PlayCircle, ShieldCheck } from 'lucide-react';

export const DecisionSupport: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">Decision Support</h1>
        <p className="text-xs md:text-sm text-slate-500 mt-1">Run simulations and predict distribution changes.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-5 space-y-4">
        <h3 className="font-bold text-slate-800 text-sm md:text-base">Distribution Policy Simulation</h3>
        <p className="text-xs text-slate-500">Simulate changes in regional ration allowance guidelines and project commodity demands.</p>
        
        <div className="flex flex-wrap gap-3">
          <button 
            onClick={() => alert('Simulation started.')}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0284C7] hover:bg-[#0369A1] text-white text-xs font-bold rounded shadow-xs transition-colors"
          >
            <PlayCircle size={14} />
            <span>Simulate Rice Allocation Hike (+10%)</span>
          </button>
          
          <button 
            onClick={() => alert('Risk verification check.')}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 text-xs font-bold rounded transition-colors"
          >
            <ShieldCheck size={14} />
            <span>Verify Distribution Compliance</span>
          </button>
        </div>
      </div>
    </div>
  );
};
