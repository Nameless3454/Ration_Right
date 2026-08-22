import React from 'react';
import { Shield, Sliders, Bell } from 'lucide-react';

export const Settings: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">System Settings</h1>
        <p className="text-xs md:text-sm text-slate-500 mt-1">Configure automated rules, threshold controls, and API configurations.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-5 divide-y divide-slate-100 space-y-4">
        <div className="flex gap-4 items-start pb-4">
          <Sliders className="text-[#0284C7] mt-1" size={20} />
          <div>
            <h4 className="font-bold text-slate-800 text-sm">Anomaly Detection Thresholds</h4>
            <p className="text-xs text-slate-400 mt-0.5">Define time deltas and transaction success margins to flag suspicious FPS centers.</p>
          </div>
        </div>

        <div className="flex gap-4 items-start py-4">
          <Shield className="text-green-600 mt-1" size={20} />
          <div>
            <h4 className="font-bold text-slate-800 text-sm">Security & Access Tokens</h4>
            <p className="text-xs text-slate-400 mt-0.5">Rotate operator tokens and configure dual-factor biometric settings.</p>
          </div>
        </div>

        <div className="flex gap-4 items-start pt-4">
          <Bell className="text-orange-500 mt-1" size={20} />
          <div>
            <h4 className="font-bold text-slate-800 text-sm">Notification Dispatches</h4>
            <p className="text-xs text-slate-400 mt-0.5">Send alerts automatically via SMS/Email to regional food security offices.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
