import React from 'react';
import { District } from '../types';
import { StatusBadge } from './StatusBadge';

interface DistributionTableProps {
  districts: District[];
}

export const DistributionTable: React.FC<DistributionTableProps> = ({ districts }) => {
  return (
    <div className="overflow-x-auto border border-slate-100 rounded-lg">
      <table className="w-full text-left border-collapse text-xs md:text-sm">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold tracking-wider text-[10px] uppercase">
            <th className="py-3 px-4 font-bold">District</th>
            <th className="py-3 px-4 font-bold">FPS Centers</th>
            <th className="py-3 px-4 font-bold">Distributions</th>
            <th className="py-3 px-4 font-bold">Transactions</th>
            <th className="py-3 px-4 font-bold">Status</th>
          </tr>
        </thead>
        <tbody>
          {districts.map((item) => (
            <tr
              key={item.name}
              className="border-b border-slate-50 hover:bg-slate-50/70 transition-colors text-slate-700"
            >
              <td className="py-3 px-4 font-semibold text-slate-800">{item.name}</td>
              <td className="py-3 px-4 tabular-nums">{item.fpsCenters}</td>
              <td className="py-3 px-4 font-medium tabular-nums">{item.distributionsKg.toLocaleString()} kg</td>
              <td className="py-3 px-4 tabular-nums">{item.transactions.toLocaleString()}</td>
              <td className="py-3 px-4">
                <StatusBadge type={item.status} text={item.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
