import React from 'react';

interface StatusBadgeProps {
  type: string;
  text: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ type, text }) => {
  const getColors = () => {
    switch (type.toLowerCase()) {
      case 'success':
      case 'healthy':
      case 'verified':
      case 'resolved':
      case 'active':
      case 'open':
        return 'bg-[#F0FDF4] text-[#166534] border-[#DCFCE7]';
      case 'warning':
      case 'pending':
      case 'medium':
        return 'bg-[#FFF7ED] text-[#9A3412] border-[#FFEDD5]';
      case 'error':
      case 'critical':
      case 'high':
      case 'flagged':
      case 'suspended':
        return 'bg-[#FEF2F2] text-[#991B1B] border-[#FEE2E2]';
      case 'info':
      case 'reviewing':
      case 'acknowledged':
        return 'bg-[#EFF6FF] text-[#1E40AF] border-[#DBEAFE]';
      case 'low':
      case 'unverified':
      case 'under review':
        return 'bg-[#F0F9FF] text-[#0369A1] border-[#E0F2FE]';
      default:
        return 'bg-gray-50 text-gray-600 border-gray-200';
    }
  };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded border text-xs font-semibold ${getColors()}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
      {text}
    </span>
  );
};
