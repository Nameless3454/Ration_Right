import React from 'react';
import { ShieldAlert, AlertTriangle, AlertCircle, Info } from 'lucide-react';

interface AlertSummaryProps {
  critical: number;
  high: number;
  medium: number;
  low: number;
  onSelectSeverity?: (severity: string) => void;
}

export const AlertSummary: React.FC<AlertSummaryProps> = ({
  critical,
  high,
  medium,
  low,
  onSelectSeverity
}) => {
  const severities = [
    { label: 'Critical', count: critical, bg: 'bg-[#FEF2F2]', border: 'border-[#FEE2E2]', text: 'text-[#991B1B]', icon: ShieldAlert },
    { label: 'High', count: high, bg: 'bg-[#FEF2F2]', border: 'border-[#FEE2E2]', text: 'text-[#991B1B]', icon: AlertTriangle },
    { label: 'Medium', count: medium, bg: 'bg-[#FFF7ED]', border: 'border-[#FFEDD5]', text: 'text-[#C2410C]', icon: AlertCircle },
    { label: 'Low', count: low, bg: 'bg-[#F0FDF4]', border: 'border-[#DCFCE7]', text: 'text-[#166534]', icon: Info }
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {severities.map((s) => {
        const Icon = s.icon;
        return (
          <div
            key={s.label}
            onClick={() => onSelectSeverity && onSelectSeverity(s.label)}
            className={`cursor-pointer text-center p-4 border rounded-lg hover:shadow-xs transition-shadow flex flex-col items-center justify-center ${s.bg} ${s.border}`}
          >
            <div className="flex items-center gap-1.5 mb-1.5">
              <Icon size={14} className={s.text} />
              <div className={`text-[10px] font-bold tracking-wider uppercase ${s.text}`}>{s.label}</div>
            </div>
            <div className="text-2xl font-bold text-slate-800 tabular-nums">{s.count}</div>
          </div>
        );
      })}
    </div>
  );
};
