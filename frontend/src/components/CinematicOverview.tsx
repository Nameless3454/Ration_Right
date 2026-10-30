import React, { useRef, useEffect, useState } from 'react';

interface CinematicOverviewProps {
  onSelectInvestigation?: (id: string) => void;
  onNavigate?: (route: string) => void;
}

export const CinematicOverview: React.FC<CinematicOverviewProps> = ({
  onSelectInvestigation,
  onNavigate
}) => {
  const trackRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const dashRef = useRef<HTMLDivElement>(null);
  const gaRef = useRef<HTMLDivElement>(null);
  const gbRef = useRef<HTMLDivElement>(null);
  const skipRef = useRef<HTMLButtonElement>(null);
  const replayRef = useRef<HTMLButtonElement>(null);
  const mainScrollRef = useRef<HTMLElement>(null);
  const gaugeArcRef = useRef<SVGPathElement>(null);
  const gaugeNumberRef = useRef<HTMLElement>(null);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const handleRefreshClick = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
    }, 900);
  };

  useEffect(() => {
    // Reveal stage on initial render
    const timer = setTimeout(() => {
      if (stageRef.current) stageRef.current.classList.add('ready');
    }, 120);

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
    const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a), 0, 1);
    const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

    const enterElements = [
      ...((dashRef.current?.querySelectorAll<HTMLElement>('[data-enter]')) || [])
    ].map(el => {
      const dir = el.dataset.enter;
      const offsets: Record<string, [number, number]> = {
        left: [-60, 0],
        top: [0, -24],
        up: [0, 50]
      };
      const [dx, dy] = offsets[dir || ''] || [0, 0];
      return {
        el,
        a: parseFloat(el.dataset.start || '0'),
        b: parseFloat(el.dataset.end || '1'),
        dx,
        dy
      };
    });

    const tableRows = [
      ...((dashRef.current?.querySelectorAll<HTMLElement>('.t-stagger')) || [])
    ].map((el, i) => ({ el, idx: i }));

    const cardElements = [0, 1, 2, 3, 4].map(
      i => dashRef.current?.querySelector<HTMLElement>(`#card-${i}`)
    );
    const iconElements = cardElements.map(c => c?.querySelector<HTMLElement>('.kpi-icon'));

    interface CardScatterState {
      initDx: number;
      initDy: number;
      initRot: number;
      initScale: number;
      initBlur: number;
    }

    let cardScatterOffsets: CardScatterState[] = [];

    const scatterPresets = [
      // Card 0: Total Beneficiaries (Deep Green Hero) - Top-Left
      { xRatio: 0.16, yRatio: 0.26, rot: -7, scale: 0.82, blur: 16 },
      // Card 1: Ration Distributed (Mint) - Top-Right
      { xRatio: 0.84, yRatio: 0.22, rot: 6, scale: 0.80, blur: 18 },
      // Card 2: Total Inventory (Lavender) - Bottom-Left
      { xRatio: 0.18, yRatio: 0.74, rot: -5, scale: 0.82, blur: 15 },
      // Card 3: Active Alerts (Amber) - Bottom-Right
      { xRatio: 0.82, yRatio: 0.72, rot: 7, scale: 0.78, blur: 20 },
      // Card 4: High-Risk Cases (Coral) - Bottom-Center
      { xRatio: 0.50, yRatio: 0.86, rot: -3, scale: 0.76, blur: 17 }
    ];

    const measureFLIP = () => {
      cardElements.forEach(c => {
        if (c) {
          c.style.transform = 'none';
          c.style.transition = 'none';
        }
      });

      const vw = window.innerWidth;
      const vh = window.innerHeight;

      cardScatterOffsets = cardElements.map((card, i) => {
        if (!card) return { initDx: 0, initDy: 0, initRot: 0, initScale: 1, initBlur: 0 };
        const rect = card.getBoundingClientRect();
        const gridCenterX = rect.left + rect.width / 2;
        const gridCenterY = rect.top + rect.height / 2;

        const preset = scatterPresets[i] || { xRatio: 0.5, yRatio: 0.5, rot: 0, scale: 1, blur: 10 };
        const cardW = rect.width || 220;
        const cardH = rect.height || 160;
        const pad = 24;

        // Keep scattered card safely inside viewport padding so it is NEVER clipped
        const scatterCenterX = clamp(
          vw * preset.xRatio,
          (cardW * preset.scale) / 2 + pad,
          vw - (cardW * preset.scale) / 2 - pad
        );
        const scatterCenterY = clamp(
          vh * preset.yRatio,
          (cardH * preset.scale) / 2 + pad,
          vh - (cardH * preset.scale) / 2 - pad
        );

        return {
          initDx: scatterCenterX - gridCenterX,
          initDy: scatterCenterY - gridCenterY,
          initRot: preset.rot,
          initScale: preset.scale,
          initBlur: preset.blur
        };
      });
    };

    measureFLIP();
    window.addEventListener('resize', measureFLIP, { passive: true });
    if (document.fonts) {
      document.fonts.ready.then(measureFLIP);
    }

    let cur = 0;
    let target = 0;
    let animId: number;

    const maxScroll = () => {
      if (!trackRef.current) return 1;
      return Math.max(1, trackRef.current.offsetHeight - window.innerHeight);
    };

    const handleScroll = () => {
      target = clamp(window.scrollY / maxScroll(), 0, 1);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    if (reduce) cur = target;

    const render = (p: number, time: number = 0) => {
      // 1. Hero text push-through and blur away
      const h = ease(seg(p, 0.05, 0.42));
      if (heroRef.current) {
        heroRef.current.style.opacity = (1 - h).toString();
        heroRef.current.style.filter = h > 0.01 ? `blur(${h * 28}px)` : 'none';
        heroRef.current.style.transform = `scale(${1 + h * 0.35})`;
        heroRef.current.style.pointerEvents = 'none';
      }

      // Glow drift
      if (gaRef.current) gaRef.current.style.transform = `translate(${p * 14}vw, ${p * 10}vh)`;
      if (gbRef.current) gbRef.current.style.transform = `translate(${-p * 12}vw, ${-p * 8}vh)`;

      // Skip & Replay buttons
      if (skipRef.current) {
        const skipOpacity = 1 - seg(p, 0.45, 0.70);
        skipRef.current.style.opacity = skipOpacity.toString();
        skipRef.current.style.pointerEvents = p > 0.65 ? 'none' : 'auto';
      }
      if (replayRef.current) {
        const rp = ease(seg(p, 0.90, 1.0));
        replayRef.current.style.opacity = rp.toString();
        replayRef.current.style.pointerEvents = rp > 0.5 ? 'auto' : 'none';
      }

      // 2. Camera push on whole dashboard (scale 1.04 down to 1.0)
      if (dashRef.current) {
        const cam = 1.04 - 0.04 * ease(seg(p, 0.48, 0.95));
        dashRef.current.style.transform = `scale(${cam})`;
      }

      // 3. FLIP: 5 Scattered Cards converge smoothly into the final dashboard grid
      // Cards start scattered around the perimeter (0.00 to 0.12).
      // Between 0.12 and 0.78, they glide, untilt, scale up, and sharpen into their grid slots!
      const convP = ease(seg(p, 0.12, 0.78));

      cardElements.forEach((card, i) => {
        if (!card) return;
        const scatter = cardScatterOffsets[i] || { initDx: 0, initDy: 0, initRot: 0, initScale: 1, initBlur: 0 };

        // Gentle floating drift when scattered (fades as cards converge)
        const driftFactor = 1 - convP;
        const driftX = Math.cos(time + i * 1.3) * 6 * driftFactor;
        const driftY = Math.sin(time + i * 1.7) * 8 * driftFactor;

        const curDx = scatter.initDx * (1 - convP) + driftX;
        const curDy = scatter.initDy * (1 - convP) + driftY;
        const curRot = scatter.initRot * (1 - convP);
        const curScale = scatter.initScale + (1 - scatter.initScale) * convP;
        const curBlur = scatter.initBlur * (1 - convP);
        const curOpacity = 0.55 + 0.45 * convP;

        if (convP >= 0.95) {
          card.style.transform = '';
          card.style.filter = '';
          card.style.opacity = '1';
          card.style.pointerEvents = 'auto';
        } else {
          card.style.transform = `translate(${curDx}px, ${curDy}px) rotate(${curRot}deg) scale(${curScale})`;
          card.style.filter = curBlur > 0.4 ? `blur(${curBlur}px)` : 'none';
          card.style.opacity = curOpacity.toString();
          card.style.pointerEvents = 'none';
          card.classList.remove('is-hovered');
        }
      });

      // Icon circles fade in as cards land
      const iconP = ease(seg(p, 0.68, 0.82));
      iconElements.forEach(ic => {
        if (ic) ic.style.opacity = iconP.toString();
      });

      // 4. Enter elements: Sidebar, Topbar, Header, Status, Panels
      enterElements.forEach(({ el, a, b, dx, dy }) => {
        const q = ease(seg(p, a, b));
        el.style.opacity = q.toString();
        el.style.filter = q >= 0.999 ? '' : `blur(${(1 - q) * 18}px)`;
        el.style.transform = q >= 0.999 ? '' : `translate(${dx * (1 - q)}px, ${dy * (1 - q)}px)`;
        el.style.pointerEvents = q > 0.75 ? 'auto' : 'none';
      });

      // 5. Recent Investigations table rows stagger in
      tableRows.forEach(({ el, idx }) => {
        const rowStart = 0.76 + idx * 0.05;
        const rowEnd = rowStart + 0.12;
        const rq = ease(seg(p, rowStart, rowEnd));
        el.style.opacity = rq.toString();
        el.style.filter = rq >= 0.999 ? '' : `blur(${(1 - rq) * 12}px)`;
        el.style.transform = rq >= 0.999 ? '' : `translateY(${(1 - rq) * 16}px)`;
      });

      // 6. Beneficiary Coverage: gauge draws and number counts up
      const covP = ease(seg(p, 0.80, 0.98));
      if (gaugeArcRef.current) {
        const targetOffset = 330 * (1 - 0.952 * covP);
        gaugeArcRef.current.style.strokeDashoffset = targetOffset.toString();
      }
      if (gaugeNumberRef.current) {
        gaugeNumberRef.current.textContent = `${(95.2 * covP).toFixed(1)}%`;
      }

      // 7. At p near 1, allow main area to scroll smoothly; during intro keep visible so scattered cards are never clipped
      if (mainScrollRef.current) {
        if (p >= 0.96) {
          mainScrollRef.current.style.overflowY = 'auto';
          mainScrollRef.current.style.overflowX = 'hidden';
        } else {
          mainScrollRef.current.style.overflow = 'visible';
          mainScrollRef.current.scrollTop = 0;
        }
      }
    };

    const loop = (timestamp: number) => {
      const time = (timestamp || performance.now()) * 0.0015;
      cur += (target - cur) * (reduce ? 1 : 0.07);
      if (Math.abs(target - cur) < 0.0002) cur = target;
      render(cur, time);
      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);

    const cardCleanups: (() => void)[] = [];
    cardElements.forEach(card => {
      if (!card) return;
      const onEnter = () => card.classList.add('is-hovered');
      const onLeave = () => card.classList.remove('is-hovered');
      card.addEventListener('mouseenter', onEnter);
      card.addEventListener('mouseleave', onLeave);
      cardCleanups.push(() => {
        card.removeEventListener('mouseenter', onEnter);
        card.removeEventListener('mouseleave', onLeave);
      });
    });

    return () => {
      clearTimeout(timer);
      cardCleanups.forEach(fn => fn());
      window.removeEventListener('resize', measureFLIP);
      window.removeEventListener('scroll', handleScroll);
      cancelAnimationFrame(animId);
    };
  }, []);

  const handleSkip = () => {
    const max = trackRef.current ? Math.max(1, trackRef.current.offsetHeight - window.innerHeight) : 0;
    window.scrollTo({ top: max, behavior: 'smooth' });
  };

  const handleReplay = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div style={{ position: 'relative', width: '100%', overflowX: 'hidden' }}>
      {/* Skip Button */}
      <button 
        ref={skipRef} 
        className="skip-btn" 
        onClick={handleSkip} 
        type="button" 
        aria-label="Skip cinematic intro"
      >
        Skip intro →
      </button>

      {/* Replay Pill Button */}
      <button 
        ref={replayRef} 
        className="replay-btn" 
        onClick={handleReplay} 
        type="button" 
        aria-label="Replay intro"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        <span>Replay intro</span>
      </button>

      {/* 460vh Track */}
      <div ref={trackRef} id="track" style={{ height: '460vh', width: '100%' }}></div>

      {/* ONE Fixed Cinematic Stage */}
      <div ref={stageRef} className="stage" id="stage">
        {/* Glow Blobs */}
        <div ref={gaRef} className="glow a" id="ga"></div>
        <div ref={gbRef} className="glow b" id="gb"></div>

        {/* Dashboard DOM */}
        <div ref={dashRef} id="dashboard">
          
          {/* 1. Sidebar */}
          <aside className="app-sidebar" data-enter="left" data-start=".52" data-end=".80">
            <div className="side-brand">
              <i>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
                  <path d="M12 22v-9" strokeLinecap="round" />
                  <path d="M12 13C12 7.477 7.523 3 2 3c0 5.523 4.477 10 10 10z" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M12 10c0-4.418 3.582-8 8-8 0 4.418-3.582 8-8 8z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </i>
              <div>
                <b>RationRight</b>
                <small>Food Security Platform</small>
              </div>
            </div>

            <div className="side-group">
              <h6>OVERVIEW</h6>
              <ul className="side-nav">
                <li>
                  <a className="active" onClick={() => onNavigate?.('overview')}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
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

            <div className="side-group">
              <h6>DATA</h6>
              <ul className="side-nav">
                <li>
                  <a onClick={() => onNavigate?.('beneficiaries')}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" strokeLinecap="round" />
                      <circle cx="9" cy="7" r="4" strokeLinecap="round" />
                    </svg>
                    <span>Beneficiaries</span>
                  </a>
                </li>
                <li>
                  <a onClick={() => onNavigate?.('distribution')}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" strokeLinecap="round" />
                      <line x1="3" y1="6" x2="21" y2="6" strokeLinecap="round" />
                    </svg>
                    <span>Ration Distribution</span>
                  </a>
                </li>
                <li>
                  <a onClick={() => onNavigate?.('inventory')}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <ellipse cx="12" cy="5" rx="9" ry="3" />
                      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                    </svg>
                    <span>Inventory</span>
                  </a>
                </li>
              </ul>
            </div>

            <div className="side-group">
              <h6>INTELLIGENCE</h6>
              <ul className="side-nav">
                <li>
                  <a onClick={() => onNavigate?.('analysis')}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <path d="M12 3v3m0 12v3M3 12h3m12 0h3" strokeLinecap="round" />
                    </svg>
                    <span>AI Analysis</span>
                  </a>
                </li>
                <li>
                  <a onClick={() => onNavigate?.('analytics')}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" strokeLinecap="round" />
                    </svg>
                    <span>Analytics</span>
                  </a>
                </li>
                <li>
                  <a onClick={() => onNavigate?.('alerts')}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" />
                      <path d="M13.73 21a2 2 0 0 1-3.46 0" strokeLinecap="round" />
                    </svg>
                    <span>Alerts</span>
                    <span className="side-badge">447</span>
                  </a>
                </li>
              </ul>
            </div>

            <div className="side-group">
              <h6>REPORTING</h6>
              <ul className="side-nav">
                <li>
                  <a onClick={() => onNavigate?.('reports')}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" strokeLinecap="round" />
                      <polyline points="14 2 14 8 20 8" strokeLinecap="round" />
                      <line x1="16" y1="13" x2="8" y2="13" strokeLinecap="round" />
                      <line x1="16" y1="17" x2="8" y2="17" strokeLinecap="round" />
                      <polyline points="10 9 9 9 8 9" strokeLinecap="round" />
                    </svg>
                    <span>Reports</span>
                  </a>
                </li>
              </ul>
            </div>

            <div className="side-footer">
              <div className="side-wf-card">
                <small><span className="dot"></span> AI WORKFLOW</small>
                <b>Operational</b>
                <p>Anomaly detection is running</p>
              </div>
              <div className="side-user">
                <div className="side-user-av">A</div>
                <div className="side-user-txt">
                  <b>Admin</b>
                  <small>Operator</small>
                </div>
              </div>
            </div>
          </aside>

          {/* 2. Main Scrollable Area */}
          <main ref={mainScrollRef} className="app-main" id="mainScrollArea">
            
            {/* Topbar */}
            <div className="app-topbar" data-enter="top" data-start=".58" data-end=".82">
              <div className="search-field">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <circle cx="11" cy="11" r="8" strokeLinecap="round" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" strokeLinecap="round" />
                </svg>
                <input 
                  type="text" 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search cases, FPS centers, beneficiaries..." 
                  aria-label="Search" 
                />
              </div>
              <div className="top-actions">
                <div className="chip-recent">
                  <span className="dot-live"></span>
                  <span>Data recent</span>
                </div>
                <button className="icon-btn" type="button" aria-label="Notifications">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" />
                    <path d="M13.73 21a2 2 0 0 1-3.46 0" strokeLinecap="round" />
                  </svg>
                  <span className="dot-red"></span>
                </button>
                <div className="side-user-av" style={{ width: '36px', height: '36px', fontSize: '13px' }}>A</div>
              </div>
            </div>

            {/* Header */}
            <div className="app-header" data-enter="up" data-start=".62" data-end=".86">
              <div>
                <h2>Overview</h2>
                <p>Monitor ration distribution, inventory health, and AI-detected operational risks.</p>
              </div>
              <div className="header-btns">
                <button className="btn-details" type="button" onClick={() => onNavigate?.('analytics')}>
                  Analytics
                </button>
                <button 
                  className={`btn-refresh ${isRefreshing ? 'refreshing' : ''}`} 
                  type="button" 
                  onClick={handleRefreshClick}
                >
                  <svg 
                    width="15" 
                    height="15" 
                    viewBox="0 0 24 24" 
                    fill="none" 
                    stroke="currentColor" 
                    strokeWidth="2"
                    style={{ transform: isRefreshing ? 'rotate(360deg)' : 'none', transition: 'transform 0.8s ease' }}
                  >
                    <path d="M21.5 2v6h-6" strokeLinecap="round" />
                    <path d="M2.5 22v-6h6" strokeLinecap="round" />
                    <path d="M2 11.5a10 10 0 0 1 18.8-4.3L21.5 8" strokeLinecap="round" />
                    <path d="M22 12.5a10 10 0 0 1-18.8 4.2L2.5 16" strokeLinecap="round" />
                  </svg>
                  <span>Refresh</span>
                </button>
              </div>
            </div>

            {/* Status Strip */}
            <div className="app-status" data-enter="up" data-start=".68" data-end=".90">
              <div className="status-col">
                <span className="lbl">DATA STATUS</span>
                <span className="val"><span className="dot-live"></span> Recent</span>
              </div>
              <div className="status-col">
                <span className="lbl">AI WORKFLOW</span>
                <span className="val"><span className="dot-violet"></span> Operational</span>
              </div>
              <div className="status-col">
                <span className="lbl">LAST UPDATED</span>
                <span className="val">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#7a8b84" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12 6 12 12 16 14" />
                  </svg>
                  Today, 10:24 AM
                </span>
              </div>
            </div>

            {/* 5 Cards Grid */}
            <div className="cards-grid" id="cardsGrid">
              
              {/* Card 1: Total Beneficiaries (Hero Green) */}
              <div className="kpi-card hero-kpi" id="card-0" onClick={() => onNavigate?.('beneficiaries')} style={{ cursor: 'pointer' }}>
                <div className="kpi-head">
                  <span className="kpi-label">TOTAL<br />BENEFICIARIES</span>
                  <div className="kpi-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" strokeLinecap="round" />
                      <circle cx="9" cy="7" r="4" strokeLinecap="round" />
                      <path d="M23 21v-2a4 4 0 0 0-3-3.87" strokeLinecap="round" />
                    </svg>
                  </div>
                </div>
                <div>
                  <div className="kpi-num">24,582</div>
                  <div className="kpi-footer">
                    <span className="trend-pill">↑ 3.2%</span>
                    <span>vs last 7 days</span>
                  </div>
                  <div className="kpi-sub" style={{ marginTop: '4px', fontSize: '12px' }}>23,410 active</div>
                </div>
              </div>

              {/* Card 2: Ration Distributed */}
              <div className="kpi-card" id="card-1" onClick={() => onNavigate?.('distribution')} style={{ cursor: 'pointer' }}>
                <div className="kpi-head">
                  <span className="kpi-label">RATION<br />DISTRIBUTED</span>
                  <div className="kpi-icon tint-g">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" strokeLinecap="round" />
                      <line x1="3" y1="6" x2="21" y2="6" strokeLinecap="round" />
                    </svg>
                  </div>
                </div>
                <div>
                  <div className="kpi-num">43,450.5<small>kg</small></div>
                  <div className="kpi-footer">
                    <span className="trend-pill g">↑ 9.7%</span>
                    <span>vs last 7 days</span>
                  </div>
                  <div className="kpi-sub" style={{ marginTop: '4px', fontSize: '12px' }}>4,520 records</div>
                </div>
              </div>

              {/* Card 3: Total Inventory */}
              <div className="kpi-card" id="card-2" onClick={() => onNavigate?.('inventory')} style={{ cursor: 'pointer' }}>
                <div className="kpi-head">
                  <span className="kpi-label">TOTAL<br />INVENTORY</span>
                  <div className="kpi-icon tint-v">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <ellipse cx="12" cy="5" rx="9" ry="3" />
                      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                    </svg>
                  </div>
                </div>
                <div>
                  <div className="kpi-num">79,61,167.9<small>kg</small></div>
                  <div className="kpi-footer">
                    <span className="trend-pill g">↑ 2.1%</span>
                    <span>vs last 7 days</span>
                  </div>
                  <div className="kpi-sub" style={{ marginTop: '4px', fontSize: '12px' }}>7.9M total</div>
                </div>
              </div>

              {/* Card 4: Active Alerts */}
              <div className="kpi-card" id="card-3" onClick={() => onNavigate?.('alerts')} style={{ cursor: 'pointer' }}>
                <div className="kpi-head">
                  <span className="kpi-label">ACTIVE<br />ALERTS</span>
                  <div className="kpi-icon tint-a">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" />
                      <path d="M13.73 21a2 2 0 0 1-3.46 0" strokeLinecap="round" />
                    </svg>
                  </div>
                </div>
                <div>
                  <div className="kpi-num">447</div>
                  <div className="kpi-footer">
                    <span className="trend-pill g">↓ 12.4%</span>
                    <span>vs last 7 days</span>
                  </div>
                  <div className="kpi-sub" style={{ marginTop: '4px', fontSize: '12px' }}>Requiring attention</div>
                </div>
              </div>

              {/* Card 5: High-Risk Cases */}
              <div className="kpi-card" id="card-4" onClick={() => onNavigate?.('alerts')} style={{ cursor: 'pointer' }}>
                <div className="kpi-head">
                  <span className="kpi-label">HIGH-RISK<br />CASES</span>
                  <div className="kpi-icon tint-c">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" strokeLinecap="round" />
                    </svg>
                  </div>
                </div>
                <div>
                  <div className="kpi-num">148</div>
                  <div className="kpi-footer">
                    <span className="trend-pill g">↓ 8.6%</span>
                    <span>vs last 7 days</span>
                  </div>
                  <div className="kpi-sub" style={{ marginTop: '4px', fontSize: '12px' }}>Critical priority</div>
                </div>
              </div>

            </div>

            {/* Row 2: Recent Investigations + Beneficiary Coverage */}
            <div className="panels-row">
              
              {/* Recent Investigations */}
              <div className="panel-card flex-1-5" id="panelInvestigations" data-enter="up" data-start=".76" data-end=".95">
                <div className="panel-head">
                  <h3>Recent Investigations</h3>
                  <a onClick={() => onNavigate?.('analysis')} style={{ cursor: 'pointer' }}>View all →</a>
                </div>
                <div className="panel-sub">Latest detected anomalies and findings</div>
                
                <div className="table-wrap">
                  <div className="t-row header">
                    <div>CASE</div>
                    <div>ISSUE</div>
                    <div>SEVERITY</div>
                    <div>STATUS</div>
                    <div>UPDATED</div>
                  </div>
                  <div 
                    className="t-row t-stagger" 
                    data-idx="0" 
                    onClick={() => onSelectInvestigation?.('11')}
                    style={{ cursor: 'pointer' }}
                  >
                    <div style={{ fontWeight: 700 }}>11</div>
                    <div style={{ fontWeight: 600 }}>Recommendation: Human verification</div>
                    <div><span className="t-pill coral"><span className="p-dot coral"></span>High</span></div>
                    <div><span className="t-pill green"><span className="p-dot green"></span>Open</span></div>
                    <div style={{ color: 'var(--mute)', fontSize: '12px' }}>9 Aug 2026</div>
                  </div>
                  <div 
                    className="t-row t-stagger" 
                    data-idx="1" 
                    onClick={() => onSelectInvestigation?.('10')}
                    style={{ cursor: 'pointer' }}
                  >
                    <div style={{ fontWeight: 700 }}>10</div>
                    <div style={{ fontWeight: 600 }}>Distribution anomaly detected for BENX1</div>
                    <div><span className="t-pill coral"><span className="p-dot coral"></span>High</span></div>
                    <div><span className="t-pill green"><span className="p-dot green"></span>Open</span></div>
                    <div style={{ color: 'var(--mute)', fontSize: '12px' }}>9 Aug 2026</div>
                  </div>
                  <div 
                    className="t-row t-stagger" 
                    data-idx="2" 
                    onClick={() => onSelectInvestigation?.('9')}
                    style={{ cursor: 'pointer' }}
                  >
                    <div style={{ fontWeight: 700 }}>9</div>
                    <div style={{ fontWeight: 600 }}>No recent distribution activity at FPS02</div>
                    <div><span className="t-pill blue"><span className="p-dot blue"></span>Low</span></div>
                    <div><span className="t-pill green"><span className="p-dot green"></span>Open</span></div>
                    <div style={{ color: 'var(--mute)', fontSize: '12px' }}>9 Aug 2026</div>
                  </div>
                </div>
              </div>

              {/* Beneficiary Coverage */}
              <div className="panel-card flex-1" id="panelCoverage" data-enter="up" data-start=".80" data-end=".98">
                <div className="panel-head">
                  <h3>Beneficiary Coverage</h3>
                </div>
                <div className="panel-sub">Active share of all registered beneficiaries</div>

                <div className="gauge-box">
                  <svg className="gauge-svg" viewBox="0 0 250 135" aria-hidden="true">
                    <defs>
                      <linearGradient id="greenGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#062d22" />
                        <stop offset="60%" stopColor="#14654a" />
                        <stop offset="100%" stopColor="#2fa56f" />
                      </linearGradient>
                    </defs>
                    <path className="gauge-track" d="M 20 125 A 105 105 0 0 1 230 125" />
                    <path ref={gaugeArcRef} className="gauge-arc" id="gaugeArc" d="M 20 125 A 105 105 0 0 1 230 125" />
                  </svg>
                  <div className="gauge-val">
                    <strong ref={gaugeNumberRef} id="gaugeNumber">0.0%</strong>
                    <span>Active beneficiaries</span>
                  </div>
                </div>

                <div className="gauge-legend">
                  <div><span className="legend-dot active"></span>Active 23,410</div>
                  <div style={{ color: 'var(--mute)' }}><span className="legend-dot inactive"></span>Inactive 1,172</div>
                </div>
              </div>

            </div>

            {/* Row 3: Distribution Overview + Active Alerts Banner */}
            <div className="panels-row" data-enter="up" data-start=".84" data-end=".99" style={{ marginBottom: '24px' }}>
              
              {/* Distribution Overview */}
              <div className="panel-card flex-1-5">
                <div className="panel-head">
                  <h3>Distribution Overview</h3>
                  <a onClick={() => onNavigate?.('distribution')} style={{ cursor: 'pointer' }}>View all →</a>
                </div>
                <div className="panel-sub">Activity across districts</div>

                {/* Bars comparison */}
                <div className="bars-container" style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around', gap: '12px', height: '170px', padding: '10px 0 6px 0' }}>
                  <div className="bar-column">
                    <span className="bar-pill-value">8,420</span>
                    <div className="bar-capsule bar-1" style={{ height: '140px', width: '52px', borderRadius: '999px', background: 'linear-gradient(180deg, #14654a 0%, #062d22 100%)' }} title="Lucknow: 8,420 kg"></div>
                    <span className="bar-name">Lucknow</span>
                  </div>
                  <div className="bar-column">
                    <span className="bar-pill-value">6,210</span>
                    <div className="bar-capsule bar-2" style={{ height: '105px', width: '52px', borderRadius: '999px', background: 'linear-gradient(180deg, #238b60 0%, #11593f 100%)' }} title="Delhi: 6,210 kg"></div>
                    <span className="bar-name">Delhi</span>
                  </div>
                  <div className="bar-column">
                    <span className="bar-pill-value">4,890</span>
                    <div className="bar-capsule bar-3" style={{ height: '82px', width: '52px', borderRadius: '999px', background: 'linear-gradient(180deg, #37b77e 0%, #1e875a 100%)' }} title="Gwalior: 4,890 kg"></div>
                    <span className="bar-name">Gwalior</span>
                  </div>
                  <div className="bar-column">
                    <span className="bar-pill-value">3,765</span>
                    <div className="bar-capsule bar-4" style={{ height: '64px', width: '52px', borderRadius: '999px', background: 'linear-gradient(180deg, #8fe0b6 0%, #46be87 100%)' }} title="Aurangabad: 3,765 kg"></div>
                    <span className="bar-name">Aurangabad</span>
                  </div>
                  <div className="bar-column">
                    <span className="bar-pill-value">2,980</span>
                    <div className="bar-capsule bar-5" style={{ height: '50px', width: '52px', borderRadius: '999px', background: 'repeating-linear-gradient(-45deg, #a7d3bf, #a7d3bf 6px, #c8e8d8 6px, #c8e8d8 12px)' }} title="East Delhi: 2,980 kg"></div>
                    <span className="bar-name">East Delhi</span>
                  </div>
                </div>

                {/* District breakdown table */}
                <div style={{ borderTop: '1px solid #f0f4f2', paddingTop: '10px', marginTop: '10px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1.2fr 1fr', padding: '6px 8px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--label-muted)' }}>
                    <div>DISTRICT</div>
                    <div>FPS CENTERS</div>
                    <div>DISTRIBUTIONS</div>
                    <div>TRANSACTIONS</div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1.2fr 1fr', padding: '8px', fontSize: '13px', borderBottom: '1px solid #f7faf8' }}>
                    <div style={{ fontWeight: 700, color: 'var(--ink)' }}>Lucknow</div>
                    <div style={{ color: '#40544c' }}>124</div>
                    <div style={{ fontWeight: 700, color: 'var(--ink)' }}>8,420 kg</div>
                    <div style={{ color: '#40544c' }}>1,245</div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1.2fr 1fr', padding: '8px', fontSize: '13px', borderBottom: '1px solid #f7faf8' }}>
                    <div style={{ fontWeight: 700, color: 'var(--ink)' }}>Delhi</div>
                    <div style={{ color: '#40544c' }}>98</div>
                    <div style={{ fontWeight: 700, color: 'var(--ink)' }}>6,210 kg</div>
                    <div style={{ color: '#40544c' }}>982</div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1.2fr 1fr', padding: '8px', fontSize: '13px' }}>
                    <div style={{ fontWeight: 700, color: 'var(--ink)' }}>Gwalior</div>
                    <div style={{ color: '#40544c' }}>76</div>
                    <div style={{ fontWeight: 700, color: 'var(--ink)' }}>4,890 kg</div>
                    <div style={{ color: '#40544c' }}>731</div>
                  </div>
                </div>
              </div>

              {/* Active Alerts Banner Card */}
              <div 
                className="panel-card flex-1"
                onClick={() => onNavigate?.('alerts')}
                style={{
                  background: 'linear-gradient(135deg, #2a1b8f 0%, #5b3df5 55%, #8f6bff 100%)',
                  color: '#ffffff',
                  position: 'relative',
                  overflow: 'hidden',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  minHeight: '260px'
                }}
              >
                {/* Decorative concentric rings */}
                <div style={{ position: 'absolute', right: '-40px', top: '-40px', width: '220px', height: '220px', borderRadius: '50%', border: '1.5px solid rgba(255,255,255,0.18)', pointerEvents: 'none' }} />
                <div style={{ position: 'absolute', right: '-80px', top: '-80px', width: '300px', height: '300px', borderRadius: '50%', border: '1.5px solid rgba(255,255,255,0.12)', pointerEvents: 'none' }} />
                <div style={{ position: 'absolute', right: '-120px', top: '-120px', width: '380px', height: '380px', borderRadius: '50%', border: '1.5px solid rgba(255,255,255,0.08)', pointerEvents: 'none' }} />

                <div style={{ position: 'relative', zIndex: 2 }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.85)' }}>
                    ACTIVE ALERTS
                  </span>
                  <div style={{ fontSize: '54px', fontWeight: 800, fontFamily: 'var(--f-display)', lineHeight: 1.05, marginTop: '16px', letterSpacing: '-0.03em' }}>
                    447
                  </div>
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'rgba(255,255,255,0.22)', padding: '4px 10px', borderRadius: '999px', fontSize: '12px', fontWeight: 700, marginTop: '8px' }}>
                    ↓ 12.4% vs last 7 days
                  </div>
                </div>

                <div style={{ position: 'relative', zIndex: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.15)', paddingTop: '12px', marginTop: '16px' }}>
                  <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.85)' }}>148 require immediate review</span>
                  <span style={{ fontSize: '12px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    Open Alerts →
                  </span>
                </div>
              </div>

            </div>

          </main>
        </div>

        {/* Foreground Hero Push-Through Overlay */}
        <div ref={heroRef} className="hero" id="hero">
          <div>
            <div className="pill-badge">
              <i>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round">
                  <path d="M12 21v-9" strokeLinecap="round" />
                  <path d="M12 13C12 7.477 7.523 3 2 3c0 5.523 4.477 10 10 10z" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M12 10c0-4.418 3.582-8 8-8 0 4.418-3.582 8-8 8z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </i>
              <span><b>RationRight</b><small>FOOD SECURITY PLATFORM</small></span>
            </div>
            <h1 className="hero-title">Every grain.<br />Accounted for.</h1>
            <p className="hero-sub">AI-powered intelligence for transparent ration distribution.</p>
          </div>
          <div className="scroll-hint">
            SCROLL TO REVEAL DASHBOARD
            <div className="mouse-icon"></div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CinematicOverview;
