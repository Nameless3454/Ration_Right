import React, { useState, useEffect } from 'react';

interface OverviewProps {
  onSelectInvestigation: (id: string) => void;
  onNavigate: (route: string) => void;
  searchQuery: string;
}

export const Overview: React.FC<OverviewProps> = ({
  onSelectInvestigation,
  onNavigate,
  searchQuery
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [progress, setProgress] = useState(0);

  // Targets for count-up
  const TARGETS = {
    beneficiaries: 24582,
    distributed: 43450.5,
    inventory: 7961167.9,
    alerts: 447,
    highRisk: 148,
    coveragePercent: 95.2,
    maxGaugeCircumference: 330
  };

  useEffect(() => {
    let startTime: number | null = null;
    const duration = 1700;
    let animId: number;

    const tick = (currentTime: number) => {
      if (!startTime) startTime = currentTime;
      const elapsed = currentTime - startTime;
      const t = Math.min(elapsed / duration, 1);
      // easeOutQuart: 1 - (1 - t)^4
      const eased = 1 - Math.pow(1 - t, 4);
      setProgress(eased);

      if (t < 1) {
        animId = requestAnimationFrame(tick);
      }
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isRefreshing]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
    }, 950);
  };

  // Formatters
  const formatIndian = (val: number) => {
    const parts = (val * progress).toFixed(1).split('.');
    const integerPart = parts[0];
    const decimalPart = parts[1];
    let lastThree = integerPart.substring(integerPart.length - 3);
    const otherNumbers = integerPart.substring(0, integerPart.length - 3);
    if (otherNumbers !== '') {
      lastThree = ',' + lastThree;
    }
    return otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + lastThree + '.' + decimalPart;
  };

  const formatDec = (val: number) => {
    const parts = (val * progress).toFixed(1).split('.');
    return parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + parts[1];
  };

  const formatInt = (val: number) => {
    return Math.round(val * progress).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  };

  const cases = [
    { id: '11', title: 'Recommendation: Human verification', severity: 'High', status: 'Open', date: '9 Aug 2026' },
    { id: '10', title: 'Distribution anomaly detected for BENX1', severity: 'High', status: 'Open', date: '9 Aug 2026' },
    { id: '9', title: 'No recent distribution activity at FPS02', severity: 'Low', status: 'Open', date: '9 Aug 2026' }
  ];

  const filteredCases = cases.filter(c =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.id.includes(searchQuery)
  );

  return (
    <>
      {/* Page Header: Title + Subtitle + Action Buttons */}
      <section className="page-header fade-up-card delay-3">
        <div className="header-text">
          <h2>Overview</h2>
          <p>Monitor ration distribution, inventory health, and AI-detected operational risks.</p>
        </div>
        <div className="header-actions">
          <button 
            className="btn-outlined" 
            type="button"
            onClick={() => onNavigate('analytics')}
          >
            Analytics
          </button>
          <button 
            className={`btn-green-grad ${isRefreshing ? 'spinning' : ''}`} 
            id="refreshBtn" 
            type="button"
            onClick={handleRefresh}
          >
            <svg className="spin-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M21.5 2v6h-6" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2.5 22v-6h6" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 11.5a10 10 0 0 1 18.8-4.3L21.5 8" strokeLinecap="round"/>
              <path d="M22 12.5a10 10 0 0 1-18.8 4.2L2.5 16" strokeLinecap="round"/>
            </svg>
            <span>Refresh</span>
          </button>
        </div>
      </section>

      {/* Status Strip */}
      <section className="status-strip fade-up-card delay-4" aria-label="System status">
        <div className="status-item">
          <span className="label">DATA STATUS</span>
          <span className="value">
            <span className="dot-pulse"></span>
            <span>Recent</span>
          </span>
        </div>
        <div className="status-item">
          <span className="label">AI WORKFLOW</span>
          <span className="value">
            <span className="dot-blue-pulse"></span>
            <span>Operational</span>
          </span>
        </div>
        <div className="status-item">
          <span className="label">LAST UPDATED</span>
          <span className="value">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#7a8b84">
              <circle cx="12" cy="12" r="10" strokeLinecap="round"/>
              <polyline points="12 6 12 12 16 14" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span>Today, 10:24 AM</span>
          </span>
        </div>
      </section>

      {/* KPI Row (5 Auto-Fit Cards) */}
      <section className="kpi-row" aria-label="Key Performance Indicators">
        
        {/* KPI 1: Hero Total Beneficiaries */}
        <div 
          className="card kpi-card kpi-hero fade-up-card delay-5 cursor-pointer"
          onClick={() => onNavigate('beneficiaries')}
        >
          <div className="kpi-header">
            <div className="kpi-label">TOTAL<br />BENEFICIARIES</div>
            <div className="kpi-icon-wrap" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" strokeLinecap="round"/>
                <circle cx="9" cy="7" r="4" strokeLinecap="round"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" strokeLinecap="round"/>
                <path d="M16 3.13a4 4 0 0 1 0 7.75" strokeLinecap="round"/>
              </svg>
            </div>
          </div>
          <div>
            <div className="kpi-value num-display" id="kpiBeneficiaries">
              {formatInt(TARGETS.beneficiaries)}
            </div>
            <div className="kpi-footer">
              <span className="trend-pill positive-white">↑ 3.2%</span>
              <span className="kpi-subtext">vs last 7 days</span>
            </div>
            <div className="kpi-subtext" style={{ marginTop: '6px', fontSize: '12px', fontWeight: 600, color: 'rgba(255,255,255,0.9)' }}>
              23,410 active
            </div>
          </div>
        </div>

        {/* KPI 2: Ration Distributed */}
        <div 
          className="card kpi-card fade-up-card delay-6 cursor-pointer"
          onClick={() => onNavigate('distribution')}
        >
          <div className="kpi-header">
            <div className="kpi-label">RATION<br />DISTRIBUTED</div>
            <div className="kpi-icon-wrap tint-green" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" strokeLinecap="round"/>
                <line x1="3" y1="6" x2="21" y2="6" strokeLinecap="round"/>
                <path d="M16 10a4 4 0 0 1-8 0" strokeLinecap="round"/>
              </svg>
            </div>
          </div>
          <div>
            <div className="kpi-value num-display">
              <span>{formatDec(TARGETS.distributed)}</span>
              <span className="kpi-unit">kg</span>
            </div>
            <div className="kpi-footer">
              <span className="trend-pill positive">↑ 9.7%</span>
              <span className="kpi-subtext">vs last 7 days</span>
            </div>
            <div className="kpi-subtext" style={{ marginTop: '6px', fontSize: '12px', fontWeight: 600 }}>
              4,520 records
            </div>
          </div>
        </div>

        {/* KPI 3: Total Inventory */}
        <div 
          className="card kpi-card fade-up-card delay-7 cursor-pointer"
          onClick={() => onNavigate('inventory')}
        >
          <div className="kpi-header">
            <div className="kpi-label">TOTAL<br />INVENTORY</div>
            <div className="kpi-icon-wrap tint-violet" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <ellipse cx="12" cy="5" rx="9" ry="3"/>
                <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
              </svg>
            </div>
          </div>
          <div>
            <div className="kpi-value num-display">
              <span>{formatIndian(TARGETS.inventory)}</span>
              <span className="kpi-unit">kg</span>
            </div>
            <div className="kpi-footer">
              <span className="trend-pill positive">↑ 2.1%</span>
              <span className="kpi-subtext">vs last 7 days</span>
            </div>
            <div className="kpi-subtext" style={{ marginTop: '6px', fontSize: '12px', fontWeight: 600 }}>
              7.9M total
            </div>
          </div>
        </div>

        {/* KPI 4: Active Alerts */}
        <div 
          className="card kpi-card fade-up-card delay-8 cursor-pointer"
          onClick={() => onNavigate('alerts')}
        >
          <div className="kpi-header">
            <div className="kpi-label">ACTIVE<br />ALERTS</div>
            <div className="kpi-icon-wrap tint-amber" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0" strokeLinecap="round"/>
              </svg>
            </div>
          </div>
          <div>
            <div className="kpi-value num-display">
              {formatInt(TARGETS.alerts)}
            </div>
            <div className="kpi-footer">
              <span className="trend-pill positive">↓ 12.4%</span>
              <span className="kpi-subtext">vs last 7 days</span>
            </div>
            <div className="kpi-subtext" style={{ marginTop: '6px', fontSize: '12px', fontWeight: 600 }}>
              Requiring attention
            </div>
          </div>
        </div>

        {/* KPI 5: High-Risk Cases */}
        <div 
          className="card kpi-card fade-up-card delay-9 cursor-pointer"
          onClick={() => onNavigate('alerts')}
        >
          <div className="kpi-header">
            <div className="kpi-label">HIGH-RISK<br />CASES</div>
            <div className="kpi-icon-wrap tint-coral" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
          </div>
          <div>
            <div className="kpi-value num-display">
              {formatInt(TARGETS.highRisk)}
            </div>
            <div className="kpi-footer">
              <span className="trend-pill positive">↓ 8.6%</span>
              <span className="kpi-subtext">vs last 7 days</span>
            </div>
            <div className="kpi-subtext" style={{ marginTop: '6px', fontSize: '12px', fontWeight: 600 }}>
              Critical priority
            </div>
          </div>
        </div>

      </section>

      {/* Row 2: Investigations + Beneficiary Coverage */}
      <section className="split-row">

        {/* Recent Investigations Table Card (flex 1.5) */}
        <div className="card flex-1-5 fade-up-card delay-6">
          <div className="card-title-row">
            <h3>Recent Investigations</h3>
            <a 
              href="#analysis" 
              onClick={(e) => { e.preventDefault(); onNavigate('analysis'); }} 
              className="link-action"
            >
              <span>View all</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <line x1="5" y1="12" x2="19" y2="12" strokeLinecap="round"/>
                <polyline points="12 5 19 12 12 19" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </a>
          </div>
          <div className="card-subtitle">Latest detected anomalies and findings</div>

          <div className="table-container">
            <div className="grid-table" role="table" aria-label="Recent Investigations">
              <div className="grid-row header-row" role="row">
                <div role="columnheader">CASE</div>
                <div role="columnheader">ISSUE</div>
                <div role="columnheader">SEVERITY</div>
                <div role="columnheader">STATUS</div>
                <div role="columnheader">UPDATED</div>
              </div>

              {filteredCases.map((c) => (
                <div 
                  key={c.id} 
                  className="grid-row cursor-pointer" 
                  role="row"
                  onClick={() => onSelectInvestigation(c.id)}
                >
                  <div className="case-id" role="cell">{c.id}</div>
                  <div className="case-issue" role="cell">{c.title}</div>
                  <div role="cell">
                    <span className={`table-pill ${c.severity === 'High' ? 'pill-coral-tint' : 'pill-blue-tint'}`}>
                      <span className={`row-dot ${c.severity === 'High' ? 'coral' : 'blue'}`}></span>
                      <span>{c.severity}</span>
                    </span>
                  </div>
                  <div role="cell">
                    <span className="table-pill pill-green-tint">
                      <span className="row-dot green"></span>
                      <span>{c.status}</span>
                    </span>
                  </div>
                  <div style={{ color: 'var(--muted)', fontSize: '12px' }} role="cell">{c.date}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Beneficiary Coverage Card (flex 1) */}
        <div className="card flex-1 fade-up-card delay-7">
          <div className="card-title-row">
            <h3>Beneficiary Coverage</h3>
          </div>
          <div className="card-subtitle">Active share of all registered beneficiaries</div>

          <div className="coverage-card-inner">
            <div className="gauge-wrapper">
              <svg className="gauge-svg" viewBox="0 0 250 250" aria-hidden="true">
                <defs>
                  <linearGradient id="greenGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#062d22" />
                    <stop offset="60%" stopColor="#14654a" />
                    <stop offset="100%" stopColor="#2fa56f" />
                  </linearGradient>
                  <pattern id="hatchedTrack" width="6" height="6" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
                    <line x1="0" y1="0" x2="0" y2="6" stroke="#c0d0c8" strokeWidth="2.5" />
                  </pattern>
                </defs>
                <path className="gauge-track" stroke="url(#hatchedTrack)" d="M 20 125 A 105 105 0 0 1 230 125" />
                <path 
                  className="gauge-fill" 
                  d="M 20 125 A 105 105 0 0 1 230 125" 
                  style={{
                    strokeDasharray: 330,
                    strokeDashoffset: TARGETS.maxGaugeCircumference * (1 - (TARGETS.coveragePercent / 100) * progress)
                  }}
                />
              </svg>
              <div className="gauge-center-text">
                <div className="gauge-percent num-display">
                  <span>{(TARGETS.coveragePercent * progress).toFixed(1)}</span>%
                </div>
                <div className="gauge-sub">Active beneficiaries</div>
              </div>
            </div>

            <div className="gauge-legend">
              <div className="legend-item">
                <span className="legend-indicator active"></span>
                <span>Active 23,410</span>
              </div>
              <div className="legend-item">
                <span className="legend-indicator inactive"></span>
                <span>Inactive 1,172</span>
              </div>
            </div>
          </div>
        </div>

      </section>

      {/* Row 3: Distribution Overview + Active Alerts */}
      <section className="split-row">

        {/* Distribution Overview Card (flex 1.5) */}
        <div className="card flex-1-5 fade-up-card delay-8">
          <div className="card-title-row">
            <h3>Distribution Overview</h3>
            <a 
              href="#distribution" 
              onClick={(e) => { e.preventDefault(); onNavigate('distribution'); }} 
              className="link-action"
            >
              <span>View all</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <line x1="5" y1="12" x2="19" y2="12" strokeLinecap="round"/>
                <polyline points="12 5 19 12 12 19" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </a>
          </div>
          <div className="card-subtitle">Activity across districts</div>

          {/* Capsule Bars (5 Districts) */}
          <div className="bars-container" aria-label="District distribution visual comparison">
            <div className="bar-column">
              <span className="bar-pill-value num-display">8,420</span>
              <div 
                className="bar-capsule bar-1" 
                style={{ height: `${150 * progress}px` }} 
                title="Lucknow: 8,420 kg"
              ></div>
              <span className="bar-name">Lucknow</span>
            </div>

            <div className="bar-column">
              <span className="bar-pill-value num-display">6,210</span>
              <div 
                className="bar-capsule bar-2" 
                style={{ height: `${111 * progress}px` }} 
                title="Delhi: 6,210 kg"
              ></div>
              <span className="bar-name">Delhi</span>
            </div>

            <div className="bar-column">
              <span className="bar-pill-value num-display">4,890</span>
              <div 
                className="bar-capsule bar-3" 
                style={{ height: `${87 * progress}px` }} 
                title="Gwalior: 4,890 kg"
              ></div>
              <span className="bar-name">Gwalior</span>
            </div>

            <div className="bar-column">
              <span className="bar-pill-value num-display">3,765</span>
              <div 
                className="bar-capsule bar-4" 
                style={{ height: `${67 * progress}px` }} 
                title="Aurangabad: 3,765 kg"
              ></div>
              <span className="bar-name">Aurangabad</span>
            </div>

            <div className="bar-column">
              <span className="bar-pill-value num-display">2,980</span>
              <div 
                className="bar-capsule bar-5" 
                style={{ height: `${53 * progress}px` }} 
                title="East Delhi: 2,980 kg"
              ></div>
              <span className="bar-name">East Delhi</span>
            </div>
          </div>

          {/* District Data Table */}
          <div className="district-table-container">
            <div className="district-grid-table" role="table" aria-label="District details">
              <div className="district-row header" role="row">
                <div role="columnheader">DISTRICT</div>
                <div role="columnheader">FPS CENTERS</div>
                <div role="columnheader">DISTRIBUTIONS</div>
                <div role="columnheader">TRANSACTIONS</div>
              </div>
              <div className="district-row" role="row">
                <div className="district-name" role="cell">Lucknow</div>
                <div className="district-fps" role="cell">124</div>
                <div className="district-kg" role="cell">8,420 kg</div>
                <div className="district-tx" role="cell">1,245</div>
              </div>
              <div className="district-row" role="row">
                <div className="district-name" role="cell">Delhi</div>
                <div className="district-fps" role="cell">98</div>
                <div className="district-kg" role="cell">6,210 kg</div>
                <div className="district-tx" role="cell">982</div>
              </div>
              <div className="district-row" role="row">
                <div className="district-name" role="cell">Gwalior</div>
                <div className="district-fps" role="cell">76</div>
                <div className="district-kg" role="cell">4,890 kg</div>
                <div className="district-tx" role="cell">731</div>
              </div>
              <div className="district-row" role="row">
                <div className="district-name" role="cell">Aurangabad</div>
                <div className="district-fps" role="cell">64</div>
                <div className="district-kg" role="cell">3,765 kg</div>
                <div className="district-tx" role="cell">612</div>
              </div>
              <div className="district-row" role="row">
                <div className="district-name" role="cell">East Delhi</div>
                <div className="district-fps" role="cell">52</div>
                <div className="district-kg" role="cell">2,980 kg</div>
                <div className="district-tx" role="cell">487</div>
              </div>
            </div>
          </div>

        </div>

        {/* Violet Active Alerts Card (flex 1) */}
        <div className="card flex-1 violet-alerts-card fade-up-card delay-9">
          <div className="floating-glow" aria-hidden="true"></div>
          <div className="violet-rings" aria-hidden="true">
            <div className="ring-outer"></div>
            <div className="ring-inner"></div>
          </div>

          <div>
            <div className="violet-header">ACTIVE ALERTS</div>
            <div className="violet-main">
              <div className="giant-alert-num num-display">
                {formatInt(TARGETS.alerts)}
              </div>
              <span className="violet-trend-chip">↓ 12.4% vs last 7 days</span>
            </div>

            <div className="segmented-bar-wrap">
              <div className="segmented-bar-label">
                <span>148 high-risk</span>
                <span>299 other</span>
              </div>
              <div className="segmented-track" role="progressbar" aria-valuenow={148} aria-valuemin={0} aria-valuemax={447}>
                <div 
                  className="seg-coral" 
                  style={{ width: `${(148 / 447) * 100 * progress}%` }}
                ></div>
                <div className="seg-other"></div>
              </div>
            </div>
          </div>

          <button 
            className="btn-white-alert" 
            type="button"
            onClick={() => onNavigate('alerts')}
          >
            <span>Review alerts</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <line x1="5" y1="12" x2="19" y2="12" strokeLinecap="round"/>
              <polyline points="12 5 19 12 12 19" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

      </section>
    </>
  );
};
