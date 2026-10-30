import React from 'react';

interface SidebarProps {
  activeRoute: string;
  onNavigate: (route: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeRoute,
  onNavigate
}) => {
  return (
    <aside className="sidebar fade-up-card delay-1" aria-label="Main Navigation">
      {/* Brand Header */}
      <a 
        href="#overview" 
        onClick={(e) => { e.preventDefault(); onNavigate('overview'); }} 
        className="brand-header"
      >
        <div className="brand-logo-tile">
          {/* Leaf / Seed sprout icon */}
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M12 22v-9" strokeLinecap="round" />
            <path d="M12 13C12 7.477 7.523 3 2 3c0 5.523 4.477 10 10 10z" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M12 10c0-4.418 3.582-8 8-8 0 4.418-3.582 8-8 8z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="brand-text">
          <h1>RationRight</h1>
          <p>Food Security Platform</p>
        </div>
      </a>

      {/* Navigation Group: OVERVIEW */}
      <div className="nav-group">
        <div className="section-label">OVERVIEW</div>
        <ul className="nav-list">
          <li>
            <a 
              href="#overview" 
              onClick={(e) => { e.preventDefault(); onNavigate('overview'); }} 
              className={`nav-link ${activeRoute === 'overview' ? 'active' : ''}`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M3 20h18" strokeLinecap="round" />
                <path d="M6 16v-4" strokeLinecap="round" />
                <path d="M12 16V8" strokeLinecap="round" />
                <path d="M18 16v-9" strokeLinecap="round" />
              </svg>
              <span>Overview</span>
            </a>
          </li>
        </ul>
      </div>

      {/* Navigation Group: DATA */}
      <div className="nav-group">
        <div className="section-label">DATA</div>
        <ul className="nav-list">
          <li>
            <a 
              href="#beneficiaries" 
              onClick={(e) => { e.preventDefault(); onNavigate('beneficiaries'); }} 
              className={`nav-link ${activeRoute === 'beneficiaries' ? 'active' : ''}`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="9" cy="7" r="4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" strokeLinecap="round" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" strokeLinecap="round" />
              </svg>
              <span>Beneficiaries</span>
            </a>
          </li>
          <li>
            <a 
              href="#distribution" 
              onClick={(e) => { e.preventDefault(); onNavigate('distribution'); }} 
              className={`nav-link ${activeRoute === 'distribution' ? 'active' : ''}`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" strokeLinecap="round" strokeLinejoin="round" />
                <line x1="3" y1="6" x2="21" y2="6" strokeLinecap="round" />
                <path d="M16 10a4 4 0 0 1-8 0" strokeLinecap="round" />
              </svg>
              <span>Ration Distribution</span>
            </a>
          </li>
          <li>
            <a 
              href="#inventory" 
              onClick={(e) => { e.preventDefault(); onNavigate('inventory'); }} 
              className={`nav-link ${activeRoute === 'inventory' ? 'active' : ''}`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <ellipse cx="12" cy="5" rx="9" ry="3" />
                <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
              </svg>
              <span>Inventory</span>
            </a>
          </li>
        </ul>
      </div>

      {/* Navigation Group: INTELLIGENCE */}
      <div className="nav-group">
        <div className="section-label">INTELLIGENCE</div>
        <ul className="nav-list">
          <li>
            <a 
              href="#analysis" 
              onClick={(e) => { e.preventDefault(); onNavigate('analysis'); }} 
              className={`nav-link ${activeRoute === 'analysis' ? 'active' : ''}`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.636 5.636l2.121 2.121m8.486 8.486l2.121 2.121M5.636 18.364l2.121-2.121m8.486-8.486l2.121-2.121" strokeLinecap="round" />
              </svg>
              <span>AI Analysis</span>
            </a>
          </li>
          <li>
            <a 
              href="#analytics" 
              onClick={(e) => { e.preventDefault(); onNavigate('analytics'); }} 
              className={`nav-link ${activeRoute === 'analytics' ? 'active' : ''}`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>Analytics</span>
            </a>
          </li>
          <li>
            <a 
              href="#alerts" 
              onClick={(e) => { e.preventDefault(); onNavigate('alerts'); }} 
              className={`nav-link ${activeRoute === 'alerts' ? 'active' : ''}`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" strokeLinecap="round" />
              </svg>
              <span>Alerts</span>
              <span className="badge-coral-pulse">447</span>
            </a>
          </li>
        </ul>
      </div>

      {/* Navigation Group: REPORTING */}
      <div className="nav-group">
        <div className="section-label">REPORTING</div>
        <ul className="nav-list">
          <li>
            <a 
              href="#reports" 
              onClick={(e) => { e.preventDefault(); onNavigate('reports'); }} 
              className={`nav-link ${activeRoute === 'reports' ? 'active' : ''}`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" strokeLinecap="round" strokeLinejoin="round" />
                <polyline points="14 2 14 8 20 8" strokeLinecap="round" strokeLinejoin="round" />
                <line x1="16" y1="13" x2="8" y2="13" strokeLinecap="round" />
                <line x1="16" y1="17" x2="8" y2="17" strokeLinecap="round" />
                <polyline points="10 9 9 9 8 9" strokeLinecap="round" />
              </svg>
              <span>Reports</span>
            </a>
          </li>
        </ul>
      </div>

      {/* Sidebar Footer: AI Workflow + Operator Chip */}
      <div className="sidebar-footer">
        <div className="workflow-card">
          <div className="rings-wrapper">
            <div className="ring-outer"></div>
            <div className="ring-inner"></div>
          </div>
          <div className="workflow-content">
            <div className="workflow-header">
              <span className="dot-pulse" style={{ background: '#7fd8aa' }}></span>
              <span>AI WORKFLOW</span>
            </div>
            <div className="workflow-status">
              <span>Operational</span>
            </div>
            <p className="workflow-desc">Anomaly detection is running</p>
          </div>
        </div>

        <div className="user-chip">
          <div className="user-avatar">A</div>
          <div className="user-info">
            <span className="user-name">Admin</span>
            <span className="user-role">Operator</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
