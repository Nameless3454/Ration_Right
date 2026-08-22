import React from 'react';
import { Investigation } from '../types';
import { StatusBadge } from './StatusBadge';

interface InvestigationTableProps {
  investigations: Investigation[];
  onRowClick: (id: string) => void;
}

export const InvestigationTable: React.FC<InvestigationTableProps> = ({
  investigations,
  onRowClick
}) => {
  return (
    <div className="overflow-x-auto border border-slate-100 rounded-lg">
      <table className="w-full text-left border-collapse text-xs md:text-sm">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold tracking-wider text-[10px] uppercase">
            <th className="py-3 px-4 font-bold">Case</th>
            <th className="py-3 px-4 font-bold">Issue</th>
            <th className="py-3 px-4 font-bold">Severity</th>
            <th className="py-3 px-4 font-bold">Status</th>
            <th className="py-3 px-4 font-bold">Updated</th>
          </tr>
        </thead>
        <tbody>
          {investigations.map((item) => (
            <tr
              key={item.id}
              onClick={() => onRowClick(item.id)}
              className="border-b border-slate-50 hover:bg-slate-50/70 transition-colors cursor-pointer text-slate-700"
            >
              <td className="py-3 px-4 font-mono font-bold text-slate-500">{item.id}</td>
              <td className="py-3 px-4 font-medium text-slate-800">{item.title}</td>
              <td className="py-3 px-4">
                <StatusBadge type={item.severity} text={item.severity} />
              </td>
              <td className="py-3 px-4">
                <StatusBadge type={item.status} text={item.status} />
              </td>
              <td className="py-3 px-4 text-xs text-slate-400">{item.updatedAt}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
