import React from 'react';
import { Menu, LayoutGrid, BarChart2, Users, Truck, Warehouse, BrainCircuit, Activity, Bell, FileText, ChevronDown } from 'lucide-react';

interface SidebarProps {
  activeRoute: string;
  onNavigate: (route: string) => void;
  isOpen: boolean;
  onToggle: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeRoute,
  onNavigate,
  isOpen,
  onToggle
}) => {
  const sections = [
    {
      title: 'Overview',
      items: [
        { label: 'Command Center', icon: LayoutGrid, id: 'command-center' },
        { label: 'Overview', icon: BarChart2, id: 'overview' }
      ]
    },
    {
      title: 'Data',
      items: [
        { label: 'Beneficiaries', icon: Users, id: 'beneficiaries' },
        { label: 'Ration Distribution', icon: Truck, id: 'distribution' },
        { label: 'Inventory', icon: Warehouse, id: 'inventory' }
      ]
    },
    {
      title: 'Intelligence',
      items: [
        { label: 'AI Analysis', icon: BrainCircuit, id: 'analysis' },
        { label: 'Analytics', icon: Activity, id: 'analytics' },
        { label: 'Alerts', icon: Bell, id: 'alerts', count: 447 }
      ]
    },
    {
      title: 'Reporting',
      items: [
        { label: 'Reports', icon: FileText, id: 'reports' }
      ]
    }
  ];

  return (
    <>
      {/* Mobile background dimming overlay */}
      {isOpen && (
        <div 
          onClick={onToggle} 
          className="fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-xs lg:hidden"
        />
      )}

      <aside className={`fixed inset-y-0 left-0 z-40 w-[252px] bg-white border-r border-slate-200 flex flex-col transition-transform duration-200 lg:translate-x-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        {/* Header brand */}
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            {/* The RationRight Exact Logo */}
            <span className="text-[#3B82F6] shrink-0" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>
                <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>
              </svg>
            </span>
            <div className="flex flex-col line-height-none">
              <span className="text-base font-bold text-slate-800 leading-none">RationRight</span>
              <span className="text-[10px] text-slate-400 mt-0.5 leading-none">Food Security Platform</span>
            </div>
          </div>
          <button onClick={onToggle} className="lg:hidden text-slate-400 hover:text-slate-600">
            <Menu size={18} />
          </button>
        </div>

        {/* Navigation lists */}
        <nav className="flex-1 overflow-y-auto px-3.5 py-4 space-y-5">
          {sections.map((sec) => (
            <div key={sec.title}>
              <h5 className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">{sec.title}</h5>
              <ul className="space-y-0.5">
                {sec.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeRoute === item.id;
                  return (
                    <li key={item.id}>
                      <button
                        onClick={() => {
                          onNavigate(item.id);
                          // Close sidebar on mobile after clicking
                          if (window.innerWidth < 1024) onToggle();
                        }}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded text-xs font-semibold transition-colors ${
                          isActive 
                            ? 'bg-[#E0F2FE] text-[#0369A1]' 
                            : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <Icon size={16} className={isActive ? 'text-[#0369A1]' : 'text-slate-400'} />
                          <span>{item.label}</span>
                        </div>
                        {item.count && (
                          <span className="px-1.5 py-0.5 bg-[#EF4444] text-white rounded-full text-[9px] font-bold">
                            {item.count}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* Footer profile area */}
        <div className="p-3 border-t border-slate-100 space-y-2 bg-slate-50/50">
          
          <div className="flex items-center justify-between px-3 py-1.5">
            <div className="flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-full bg-[#0284C7] text-white font-bold text-xs flex items-center justify-center">A</span>
              <div className="flex flex-col text-left">
                <span className="text-xs font-bold text-slate-800 leading-none">Admin</span>
                <span className="text-[10px] text-slate-400 mt-0.5 leading-none">Operator</span>
              </div>
            </div>
            <ChevronDown size={14} className="text-slate-400" />
          </div>
        </div>
      </aside>
    </>
  );
};
