import React from 'react';
import * as Icons from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  change: number;
  text: string;
  sub: string;
  iconName: keyof typeof Icons;
  iconColor: string;
  iconBg: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  change,
  text,
  sub,
  iconName,
  iconColor,
  iconBg
}) => {
  const IconComponent = Icons[iconName] as React.ComponentType<{ className?: string; size?: number }>;
  const isPositive = change >= 0;

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col justify-between hover:shadow-sm transition-shadow">
      <div className="flex items-center justify-between gap-4">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">{title}</span>
        <span 
          className="w-9 h-9 rounded flex items-center justify-center" 
          style={{ color: iconColor, backgroundColor: iconBg }}
        >
          {IconComponent && <IconComponent size={18} />}
        </span>
      </div>
      
      <div className="mt-4">
        <div className="text-2xl font-bold text-slate-900 leading-none">{value}</div>
        <div className="flex items-center gap-1.5 mt-2.5 text-xs flex-wrap">
          <span className={`font-semibold flex items-center ${isPositive ? 'text-green-600' : 'text-red-500'}`}>
            {isPositive ? '↑' : '↓'} {Math.abs(change)}%
          </span>
          <span className="text-slate-400">{text}</span>
          <span className="text-slate-300">•</span>
          <span className="text-slate-400 font-medium">{sub}</span>
        </div>
      </div>
    </div>
  );
};
