import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { TopNavbar } from './components/TopNavbar';
import { InvestigationDetailModal } from './components/InvestigationDetailModal';

// Pages
import { Overview } from './pages/Overview';
import { AIAnalysis } from './pages/AIAnalysis';
import { Alerts } from './pages/Alerts';
import { Beneficiaries } from './pages/Beneficiaries';
import { Inventory } from './pages/Inventory';
import { RationDistribution } from './pages/RationDistribution';
import { Settings } from './pages/Settings';
import { Analytics } from './pages/Analytics';
import { AIInsights } from './pages/AIInsights';
import { DecisionSupport } from './pages/DecisionSupport';
import { Reports } from './pages/Reports';
import { CommandCenter } from './pages/CommandCenter';

// Mock Data
import { mockInvestigations } from './data/mockData';
import { Investigation } from './types';

export const App: React.FC = () => {
  const [activeRoute, setActiveRoute] = useState<string>('overview');
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  // Selected investigation for modal
  const [selectedCase, setSelectedCase] = useState<Investigation | null>(null);

  const handleSelectCase = (id: string) => {
    const found = mockInvestigations.find(item => item.id === id);
    if (found) {
      setSelectedCase(found);
    }
  };

  const handleNavigate = (route: string) => {
    setActiveRoute(route);
    setSearchQuery(''); // Reset search on page change
  };

  const renderActivePage = () => {
    switch (activeRoute) {
      case 'command-center':
        return <CommandCenter onNavigate={handleNavigate} />;
      case 'overview':
        return (
          <Overview 
            onSelectInvestigation={handleSelectCase} 
            onNavigate={handleNavigate}
            searchQuery={searchQuery}
          />
        );
      case 'beneficiaries':
        return <Beneficiaries />;
      case 'distribution':
        return <RationDistribution />;
      case 'inventory':
        return <Inventory />;
      case 'analysis':
        return <AIAnalysis />;
      case 'analytics':
        return <Analytics />;
      case 'insights':
        return <AIInsights />;
      case 'alerts':
        return <Alerts />;
      case 'simulation':
        return <DecisionSupport />;
      case 'reports':
        return <Reports />;
      case 'settings':
        return <Settings />;
      default:
        return <Overview onSelectInvestigation={handleSelectCase} onNavigate={handleNavigate} searchQuery={searchQuery} />;
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex text-slate-800 font-sans">
      {/* Sidebar Navigation */}
      <Sidebar 
        activeRoute={activeRoute} 
        onNavigate={handleNavigate} 
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main Container */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-[252px]">
        {/* Top Navbar */}
        <TopNavbar 
          activeRoute={activeRoute} 
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />

        {/* Dynamic Page View Area */}
        <main className="flex-1 p-4 md:p-6 max-w-7xl w-full mx-auto">
          {renderActivePage()}
        </main>

        {/* Footer */}
        <footer className="border-t border-slate-200 px-6 py-4 bg-white text-center text-xs text-slate-400">
          <p>RationRight uses synthetic demo data. A detected anomaly is not proof of fraud — every case is recommended for human verification.</p>
        </footer>
      </div>

      {/* Case Details Modal */}
      <InvestigationDetailModal 
        investigation={selectedCase} 
        onClose={() => setSelectedCase(null)} 
      />
    </div>
  );
};

export default App;
