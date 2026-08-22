import React from 'react';
import { X, ShieldAlert, Sparkles, UserCheck, ShieldClose, CheckCircle } from 'lucide-react';
import { Investigation } from '../types';
import { StatusBadge } from './StatusBadge';

interface InvestigationDetailModalProps {
  investigation: Investigation | null;
  onClose: () => void;
}

export const InvestigationDetailModal: React.FC<InvestigationDetailModalProps> = ({
  investigation,
  onClose
}) => {
  if (!investigation) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
      <div className="bg-white border border-slate-200 rounded-lg shadow-xl w-full max-w-lg overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-slate-400">Case #{investigation.id}</span>
            <StatusBadge type={investigation.severity} text={investigation.severity} />
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors p-1">
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 flex-1 overflow-y-auto space-y-4 text-xs md:text-sm">
          <div>
            <h3 className="text-base font-bold text-slate-800 leading-tight">{investigation.title}</h3>
            <p className="text-xs text-slate-400 mt-1">Updated on {investigation.updatedAt}</p>
          </div>

          {/* Details list */}
          <div className="grid grid-cols-2 gap-3.5 bg-slate-50 p-3 rounded-lg text-xs border border-slate-100">
            <div>
              <span className="text-slate-400 block font-medium">Affected FPS</span>
              <strong className="text-slate-700">{investigation.fps}</strong>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">District</span>
              <strong className="text-slate-700">{investigation.district}</strong>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">AI Confidence</span>
              <strong className="text-[#0284C7]">{investigation.confidence}%</strong>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">Current Status</span>
              <StatusBadge type={investigation.status} text={investigation.status} />
            </div>
          </div>

          {/* Reasoning */}
          <div className="space-y-1.5">
            <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
              <Sparkles size={14} className="text-sky-500" />
              AI Reasoning & Analysis
            </h4>
            <p className="text-slate-600 text-xs leading-relaxed bg-sky-50/30 border border-sky-100/50 p-3 rounded">
              {investigation.reasoning}
            </p>
          </div>

          {/* Action */}
          <div className="space-y-1.5">
            <h4 className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
              <ShieldAlert size={14} className="text-orange-500" />
              Recommended Protocol
            </h4>
            <p className="text-slate-600 text-xs leading-relaxed bg-amber-50/20 border border-amber-100/40 p-3 rounded">
              {investigation.recommendedAction}
            </p>
          </div>
        </div>

        {/* Footer actions */}
        <div className="px-5 py-3.5 border-t border-slate-100 bg-slate-50 flex flex-wrap gap-2 justify-end">
          <button 
            onClick={onClose}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-white border border-slate-200 text-slate-600 rounded hover:bg-slate-50 transition-colors"
          >
            <ShieldClose size={14} />
            Close Case
          </button>
          <button 
            onClick={() => { alert('Assigned for regional inspection.'); onClose(); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-white border border-[#0284C7] text-[#0284C7] rounded hover:bg-sky-50/50 transition-colors"
          >
            <UserCheck size={14} />
            Assign Review
          </button>
          <button 
            onClick={() => { alert('Case marked as approved / resolved.'); onClose(); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-[#0284C7] text-white rounded hover:bg-[#0369A1] transition-colors shadow-xs"
          >
            <CheckCircle size={14} />
            Approve Action
          </button>
        </div>
      </div>
    </div>
  );
};
