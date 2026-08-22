import React, { useState } from 'react';
import { Bell, ChevronDown, Menu, User, LogOut } from 'lucide-react';

interface TopNavbarProps {
  activeRoute: string;
  onToggleSidebar: () => void;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({
  activeRoute,
  onToggleSidebar
}) => {
  const [profileOpen, setProfileOpen] = useState(false);
  const [notifsOpen, setNotifsOpen] = useState(false);

  const getPageTitle = () => {
    return activeRoute.charAt(0).toUpperCase() + activeRoute.slice(1).replace('-', ' ');
  };

  const notifications = [
    { id: '1', title: 'Critical Alert', text: 'Case #11 anomaly triggered at BENX1.', time: '5m ago', type: 'critical' },
    { id: '2', title: 'Inventory Warning', text: 'Wheat stock running low at Aurangabad.', time: '1h ago', type: 'warning' }
  ];

  return (
    <header className="sticky top-0 z-20 h-14 bg-white border-b border-slate-200 px-4 md:px-6 flex items-center justify-between gap-4">
      {/* Left side breadcrumbs */}
      <div className="flex items-center gap-3 min-w-0">
        <button onClick={onToggleSidebar} className="lg:hidden text-slate-500 p-1 hover:bg-slate-100 rounded">
          <Menu size={20} />
        </button>
        <nav className="text-xs md:text-sm font-semibold flex items-center gap-1.5 min-w-0 select-none">
          <span className="text-slate-400 font-medium">RationRight</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-800 truncate">{getPageTitle()}</span>
        </nav>
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-3">


        {/* Data Status Dot */}
        <div className="flex items-center gap-1.5 px-3 py-1 bg-slate-50 border border-slate-100 rounded-full text-xs font-semibold text-slate-600">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
          <span>Data recent</span>
        </div>

        {/* Alerts Bell */}
        <div className="relative">
          <button 
            onClick={() => setNotifsOpen(!notifsOpen)} 
            className="w-8 h-8 rounded flex items-center justify-center text-slate-500 hover:bg-slate-100 transition-colors"
          >
            <Bell size={18} />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-red-500 border border-white"></span>
          </button>

          {notifsOpen && (
            <div className="absolute right-0 mt-2 w-64 bg-white border border-slate-200 rounded-lg shadow-lg py-2 z-30">
              <h4 className="px-4 py-1 text-xs font-bold text-slate-400 uppercase tracking-wider">Recent Notifications</h4>
              <div className="divide-y divide-slate-100 mt-2">
                {notifications.map((n) => (
                  <div key={n.id} className="px-4 py-2 hover:bg-slate-50 transition-colors text-xs cursor-pointer">
                    <div className="flex justify-between font-semibold">
                      <span className={n.type === 'critical' ? 'text-red-600' : 'text-orange-500'}>{n.title}</span>
                      <span className="text-slate-400 font-normal">{n.time}</span>
                    </div>
                    <p className="text-slate-600 mt-0.5">{n.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>



        {/* Profile Avatar Dropdown */}
        <div className="relative">
          <button
            onClick={() => setProfileOpen(!profileOpen)}
            className="flex items-center gap-2 pl-1 pr-2 py-0.5 rounded-full hover:bg-slate-100 transition-colors text-left"
          >
            <span className="w-7 h-7 rounded-full bg-[#0284C7] text-white font-bold text-xs flex items-center justify-center">A</span>
            <div className="hidden lg:flex flex-col select-none">
              <span className="text-xs font-bold text-slate-800 leading-none">Admin</span>
              <span className="text-[10px] text-slate-400 mt-0.5 leading-none">Operator</span>
            </div>
            <ChevronDown size={14} className="text-slate-400 shrink-0" />
          </button>

          {profileOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white border border-slate-200 rounded-lg shadow-lg py-1 z-30 divide-y divide-slate-100">
              <div className="px-4 py-2 text-xs">
                <p className="font-bold text-slate-800">Admin Operator</p>
                <p className="text-slate-400 mt-0.5">admin@rationright.gov.in</p>
              </div>
              <div className="py-1">
                <button 
                  onClick={() => { setProfileOpen(false); alert('Profile center'); }}
                  className="w-full flex items-center gap-2 px-4 py-2 text-xs text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors text-left"
                >
                  <User size={14} />
                  <span>My Profile</span>
                </button>
              </div>
              <div className="py-1">
                <button 
                  onClick={() => { setProfileOpen(false); alert('Logged out successfully.'); }}
                  className="w-full flex items-center gap-2 px-4 py-2 text-xs text-red-600 hover:bg-red-50/50 transition-colors text-left"
                >
                  <LogOut size={14} />
                  <span>Logout</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
