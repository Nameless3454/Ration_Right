import React, { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { TopNavbar } from './components/TopNavbar';
import { InvestigationDetailModal } from './components/InvestigationDetailModal';
import { CinematicOverview } from './components/CinematicOverview';

// Pages
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

// Mock Data
import { mockInvestigations } from './data/mockData';
import { Investigation } from './types';

export const App: React.FC = () => {
  const [activeRoute, setActiveRoute] = useState<string>('overview');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCase, setSelectedCase] = useState<Investigation | null>(null);

  const handleSelectCase = (id: string) => {
    const found = mockInvestigations.find(item => item.id === id);
    if (found) {
      setSelectedCase(found);
    }
  };

  const handleNavigate = (route: string) => {
    setActiveRoute(route);
    setSearchQuery('');
  };

  const renderActivePage = () => {
    switch (activeRoute) {
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
        return null;
    }
  };

  // When on overview route: render the seamless CinematicOverview
  if (activeRoute === 'overview') {
    return (
      <>
        <CinematicOverview 
          onSelectInvestigation={handleSelectCase}
          onNavigate={handleNavigate}
        />

        <InvestigationDetailModal 
          investigation={selectedCase} 
          onClose={() => setSelectedCase(null)} 
        />
      </>
    );
  }

  // When navigating to other sub-pages (Beneficiaries, Inventory, Alerts, etc.)
  return (
    <div className="dashboard-page-wrapper" id="dashboard-root">
      <div className="blob-canvas" aria-hidden="true">
        <div className="blob blob-1"></div>
        <div className="blob blob-2"></div>
        <div className="blob blob-3"></div>
      </div>

      <div className="app-shell">
        <Sidebar 
          activeRoute={activeRoute} 
          onNavigate={handleNavigate} 
        />

        <main className="main-content">
          <TopNavbar 
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
          />

          <div key={activeRoute} className="page-cinematic-stage">
            {renderActivePage()}
          </div>
        </main>
      </div>

      <InvestigationDetailModal 
        investigation={selectedCase} 
        onClose={() => setSelectedCase(null)} 
      />
    </div>
  );
};

export default App;
