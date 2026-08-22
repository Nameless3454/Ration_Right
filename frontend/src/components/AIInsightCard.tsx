import React from 'react';
import { Sparkles, ArrowRight } from 'lucide-react';
import { StatusBadge } from './StatusBadge';

interface AIInsightCardProps {
  onViewCase: (id: string) => void;
}

export const AIInsightCard: React.FC<AIInsightCardProps> = ({ onViewCase }) => {
  return (
    <div className="flex flex-col gap-4">
      {/* Sparkles Highlight Banner */}
      <div className="flex items-center gap-2.5 p-3.5 bg-sky-50 border border-sky-100 rounded-lg text-xs font-semibold text-[#0369A1]">
        <Sparkles size={16} className="text-[#0284C7] shrink-0" />
        <span>3 distribution anomalies require human verification.</span>
      </div>

      {/* Main Insight Details */}
      <div className="border border-slate-100 bg-slate-50/50 rounded-lg p-4 flex flex-col gap-3">
        <div className="flex justify-between items-start">
          <div>
            <h4 className="font-semibold text-slate-800 text-sm">Distribution anomaly detected</h4>
            <div className="text-xs text-slate-500 mt-1 flex flex-wrap gap-x-2 gap-y-1">
              <span>FPS: <strong className="text-slate-700">BENX1</strong></span>
              <span className="text-slate-300">•</span>
              <span>District: <strong className="text-slate-700">East Delhi</strong></span>
            </div>
          </div>
          <StatusBadge type="High" text="High" />
        </div>

        <div className="flex justify-end mt-2">
          <button
            onClick={() => onViewCase('11')}
            className="flex items-center gap-1 text-xs font-bold text-[#0284C7] hover:text-[#0369A1] transition-colors"
          >
            View case <ArrowRight size={13} />
          </button>
        </div>
      </div>
    </div>
  );
};
