import React from 'react';
import { Target, Shield, AlertCircle } from 'lucide-react';

interface CommandCenterProps {
  onNavigate: (route: string) => void;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({ onNavigate }) => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">Command Center</h1>
        <p className="text-xs md:text-sm text-slate-500 mt-1">Real-time status tracking of all distribution pipelines.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div 
          onClick={() => onNavigate('analysis')}
          className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col gap-3 hover:border-[#0284C7] cursor-pointer hover:shadow-xs transition-all"
        >
          <div className="flex items-center gap-2">
            <Target className="text-[#0284C7]" size={18} />
            <h4 className="font-bold text-slate-800 text-sm">Active Agents</h4>
          </div>
          <p className="text-xs text-slate-500">4 running analysis models monitoring timing, volume, stock status, and compliance.</p>
        </div>

        <div 
          onClick={() => onNavigate('distribution')}
          className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col gap-3 hover:border-green-600 cursor-pointer hover:shadow-xs transition-all"
        >
          <div className="flex items-center gap-2">
            <Shield className="text-green-600" size={18} />
            <h4 className="font-bold text-slate-800 text-sm">Ration Distribution</h4>
          </div>
          <p className="text-xs text-slate-500">All data pipelines online. 100% database connectivity established.</p>
        </div>

        <div 
          onClick={() => onNavigate('alerts')}
          className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col gap-3 hover:border-red-500 cursor-pointer hover:shadow-xs transition-all"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="text-red-500" size={18} />
            <h4 className="font-bold text-slate-800 text-sm">Alerts</h4>
          </div>
          <p className="text-xs text-slate-500">5 cases requiring review. Live notifications are active.</p>
        </div>
      </div>
    </div>
  );
};
