import React, { useRef, useEffect } from 'react';

interface CinematicIntroProps {
  onComplete: () => void;
}

export const CinematicIntro: React.FC<CinematicIntroProps> = ({ onComplete }) => {
  const trackRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const gaRef = useRef<HTMLDivElement>(null);
  const gbRef = useRef<HTMLDivElement>(null);
  const sideRef = useRef<HTMLElement>(null);
  const topRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);
  const skipRef = useRef<HTMLButtonElement>(null);
  const cardsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Stage ready transition
    const timer = setTimeout(() => {
      if (stageRef.current) stageRef.current.classList.add('ready');
    }, 200);

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
    const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a), 0, 1);
    const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

    let cur = 0;
    let tgt = 0;
    let animId: number;

    const cardsData = [
      { x: -34, y: -26, r: -8, k: 1.2, b: 14 },
      { x: 30, y: -30, r: 7, k: 0.9, b: 9 },
      { x: -40, y: 22, r: 6, k: 0.85, b: 11 },
      { x: 38, y: 18, r: -6, k: 1.3, b: 16 },
      { x: 4, y: 38, r: 4, k: 1, b: 12 }
    ];

    const cardElements = cardsRef.current?.querySelectorAll<HTMLElement>('.intro-card');

    const maxScroll = () => {
      if (!trackRef.current) return 1;
      return Math.max(1, trackRef.current.offsetHeight - window.innerHeight);
    };

    const handleScroll = () => {
      const scrollY = window.scrollY;
      tgt = clamp(scrollY / maxScroll(), 0, 1);
      if (tgt >= 0.98) {
        // Automatically smoothly hand over to dashboard
        onComplete();
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    if (reduce) cur = tgt;

    const reveal = (el: HTMLElement | null, q: number, dy: number) => {
      if (!el) return;
      el.style.opacity = q.toString();
      el.style.filter = `blur(${(1 - q) * 18}px)`;
      el.style.transform = `translateY(${(1 - q) * dy}px)`;
    };

    const render = (p: number, t: number) => {
      const vw = window.innerWidth;
      const vh = window.innerHeight;

      // 1. Hero text push-through and blur away
      const h = ease(seg(p, 0.04, 0.34));
      if (heroRef.current) {
        heroRef.current.style.opacity = (1 - h).toString();
        heroRef.current.style.filter = `blur(${h * 28}px)`;
        heroRef.current.style.transform = `scale(${1 + h * 0.3})`;
        heroRef.current.style.pointerEvents = h > 0.8 ? 'none' : 'auto';
      }

      // 2. Floating scattered cards converge into dashboard grid
      const q = ease(seg(p, 0.08, 0.7));
      if (cardElements) {
        cardElements.forEach((card, i) => {
          const d = cardsData[i];
          const f = Math.sin(t / 1500 + i * 1.7) * 10 * (1 - q);
          card.style.transform = `translate(${(d.x * vw) / 100 * (1 - q)}px, ${
            (d.y * vh) / 100 * (1 - q) + f
          }px) rotate(${d.r * (1 - q)}deg) scale(${1 + (d.k - 1) * (1 - q)})`;
          card.style.filter = `blur(${d.b * (1 - q)}px)`;
          card.style.opacity = (0.55 + 0.45 * q).toString();
        });
      }

      // 3. Reveal Sidebar, Topbar, Header, Status Strip
      if (sideRef.current) {
        const sq = ease(seg(p, 0.5, 0.82));
        sideRef.current.style.opacity = sq.toString();
        sideRef.current.style.filter = `blur(${(1 - sq) * 18}px)`;
        sideRef.current.style.transform = `translateX(${(1 - sq) * -60}px)`;
      }

      reveal(topRef.current, ease(seg(p, 0.58, 0.86)), -24);
      reveal(headRef.current, ease(seg(p, 0.62, 0.9)), 24);
      reveal(statusRef.current, ease(seg(p, 0.7, 0.95)), 24);

      // Glow drifting
      if (gaRef.current) gaRef.current.style.transform = `translate(${p * 14}vw, ${p * 10}vh)`;
      if (gbRef.current) gbRef.current.style.transform = `translate(${-p * 12}vw, ${-p * 8}vh)`;

      // Skip button fade out
      if (skipRef.current) {
        skipRef.current.style.opacity = (1 - seg(p, 0.4, 0.6)).toString();
        skipRef.current.style.pointerEvents = p > 0.55 ? 'none' : 'auto';
      }
    };

    const loop = (timestamp: number) => {
      cur += (tgt - cur) * (reduce ? 1 : 0.07);
      if (Math.abs(tgt - cur) < 0.0002) cur = tgt;
      render(cur, reduce ? 0 : timestamp);
      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('scroll', handleScroll);
      cancelAnimationFrame(animId);
    };
  }, [onComplete]);

  const handleSkip = () => {
    onComplete();
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
  };

  return (
    <div style={{ position: 'relative', width: '100%', overflowX: 'hidden' }}>
      {/* Skip button */}
      <button 
        ref={skipRef} 
        id="skip" 
        className="intro-skip" 
        onClick={handleSkip}
        type="button"
        aria-label="Skip cinematic introduction"
      >
        Skip intro
      </button>

      {/* 460vh Scroll Track */}
      <div ref={trackRef} id="track" style={{ height: '460vh', width: '100%' }}></div>

      {/* Fixed Fullscreen Cinematic Stage */}
      <div ref={stageRef} className="intro-stage" id="stage">
        {/* Glow Blobs */}
        <div ref={gaRef} className="intro-glow a" id="ga"></div>
        <div ref={gbRef} className="intro-glow b" id="gb"></div>

        {/* Dashboard Grid Wireframe */}
        <div className="intro-app">
          {/* Sidebar */}
          <aside ref={sideRef} className="intro-side" id="side">
            <div className="intro-logo">
              <i>
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round">
                  <path d="M12 21v-9M12 12C12 8 9 6 5 6c0 4 2 6 7 6zM12 12c0-4 3-6 7-6 0 4-2 6-7 6z" />
                </svg>
              </i>
              <div>
                <b>RationRight</b>
                <small>Food Security Platform</small>
              </div>
            </div>
            <nav className="intro-nav">
              <h6>Overview</h6>
              <a>Command Center</a>
              <a className="on">Overview</a>
              <h6>Data</h6>
              <a>Beneficiaries</a>
              <a>Ration Distribution</a>
              <a>Inventory</a>
              <h6>Intelligence</h6>
              <a>AI Analysis</a>
              <a>Analytics</a>
              <a>Alerts</a>
            </nav>
          </aside>

          {/* Main Area */}
          <div className="intro-main">
            <div ref={topRef} className="intro-top" id="top">
              <span>Search cases, FPS centers, beneficiaries...</span>
              <div className="intro-chip">Data recent</div>
              <div className="intro-av">A</div>
            </div>

            <div ref={headRef} className="intro-head" id="head">
              <h2>Overview</h2>
              <p>Monitor ration distribution, inventory health, and AI-detected operational risks.</p>
            </div>

            <div ref={statusRef} className="intro-status" id="status">
              <div><em>DATA STATUS</em>Recent</div>
              <div><em>AI WORKFLOW</em>Operational</div>
              <div><em>LAST UPDATED</em>Today, 10:24 AM</div>
            </div>

            {/* Converging 5 KPI Cards */}
            <div ref={cardsRef} className="intro-cards">
              <div className="intro-card dk">
                <h6>Total beneficiaries</h6>
                <strong>24,582</strong>
                <div className="d"><b>↑ 3.2%</b>vs last 7 days</div>
                <p>23,410 active</p>
              </div>

              <div className="intro-card">
                <h6>Ration distributed</h6>
                <strong>43,450.5<small>kg</small></strong>
                <div className="d"><b>↑ 9.7%</b>vs last 7 days</div>
                <p>4,520 records</p>
              </div>

              <div className="intro-card">
                <h6>Total inventory</h6>
                <strong>79,61,167.9<small>kg</small></strong>
                <div className="d"><b>↑ 2.1%</b>vs last 7 days</div>
                <p>7.9M total</p>
              </div>

              <div className="intro-card">
                <h6>Active alerts</h6>
                <strong>447</strong>
                <div className="d"><b>↓ 12.4%</b>vs last 7 days</div>
                <p>Requiring attention</p>
              </div>

              <div className="intro-card">
                <h6>High-risk cases</h6>
                <strong>148</strong>
                <div className="d"><b>↓ 8.6%</b>vs last 7 days</div>
                <p>Critical priority</p>
              </div>
            </div>
          </div>
        </div>

        {/* Foreground Hero Headline Overlay */}
        <div ref={heroRef} className="intro-hero" id="hero">
          <div>
            <div className="intro-pill">
              <i>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round">
                  <path d="M12 21v-9M12 12C12 8 9 6 5 6c0 4 2 6 7 6zM12 12c0-4 3-6 7-6 0 4-2 6-7 6z" />
                </svg>
              </i>
              <span><b>RationRight</b><small>FOOD SECURITY PLATFORM</small></span>
            </div>
            <h1>Every grain.<br />Accounted for.</h1>
            <p className="intro-sub">AI-powered intelligence for transparent ration distribution.</p>
          </div>
          <div className="intro-hint">
            SCROLL TO REVEAL DASHBOARD
            <div className="intro-mouse"></div>
          </div>
        </div>
      </div>

      <style>{`
        .intro-stage {
          position: fixed;
          inset: 0;
          overflow: hidden;
          background: linear-gradient(135deg, #e7f0eb 0%, #e9eeee 50%, #e2e0ef 100%);
          z-index: 100;
        }
        .intro-glow {
          position: absolute;
          width: 60vmax;
          height: 60vmax;
          border-radius: 50%;
          filter: blur(90px);
          opacity: 0.55;
          will-change: transform;
          pointer-events: none;
        }
        .intro-glow.a {
          background: #bfe3cf;
          left: -15vmax;
          top: -20vmax;
        }
        .intro-glow.b {
          background: #d4cdf0;
          right: -20vmax;
          bottom: -25vmax;
        }
        .intro-app {
          position: absolute;
          inset: 0;
          display: grid;
          grid-template-columns: min(330px, 26vw) 1fr;
          gap: 28px;
          padding: 28px;
          max-width: 1560px;
          margin: 0 auto;
        }
        .intro-side, .intro-top, .intro-head, .intro-status {
          will-change: opacity, filter, transform;
        }
        .intro-side {
          background: rgba(255, 255, 255, 0.75);
          border-radius: 40px;
          padding: 36px 28px;
          box-shadow: 0 20px 60px rgba(30, 70, 50, 0.08);
          backdrop-filter: blur(20px);
          -webkit-backdrop-filter: blur(20px);
        }
        .intro-logo {
          display: flex;
          gap: 14px;
          align-items: center;
          margin-bottom: 34px;
        }
        .intro-logo i {
          width: 56px;
          height: 56px;
          border-radius: 18px;
          background: linear-gradient(135deg, #1b4a35, #348060);
          display: grid;
          place-items: center;
          box-shadow: 0 10px 24px rgba(27, 74, 53, 0.35);
          flex-shrink: 0;
        }
        .intro-logo b {
          font-size: 24px;
          letter-spacing: -0.02em;
          display: block;
          font-weight: 800;
          color: #10261c;
        }
        .intro-logo small {
          color: #5d7468;
          font-size: 14px;
          font-weight: 500;
        }
        .intro-nav {
          display: grid;
          gap: 6px;
          font-weight: 500;
          font-size: 16px;
        }
        .intro-nav h6 {
          font-weight: 600;
          font-size: 12px;
          letter-spacing: 0.2em;
          color: #5d7468;
          margin: 20px 0 8px 10px;
          text-transform: uppercase;
        }
        .intro-nav a {
          padding: 13px 18px;
          border-radius: 99px;
          display: flex;
          gap: 14px;
          align-items: center;
          color: #2b4337;
          cursor: pointer;
        }
        .intro-nav a::before {
          content: "";
          width: 16px;
          height: 16px;
          border: 2px solid #6b8377;
          border-radius: 5px;
        }
        .intro-nav a.on {
          background: linear-gradient(90deg, #1b4a35, #2f6b52);
          color: #fff;
          box-shadow: 0 12px 26px rgba(27, 74, 53, 0.3);
        }
        .intro-nav a.on::before {
          border-color: #fff;
        }
        .intro-main {
          display: flex;
          flex-direction: column;
          gap: 20px;
          min-width: 0;
        }
        .intro-top {
          display: flex;
          gap: 16px;
          align-items: center;
          padding: 16px 28px;
          border-radius: 99px;
          background: rgba(255, 255, 255, 0.75);
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          color: #5d7468;
          font-size: 14px;
          box-shadow: 0 10px 30px rgba(30, 70, 50, 0.05);
        }
        .intro-top span { flex: 1; }
        .intro-chip {
          padding: 8px 16px;
          border-radius: 99px;
          background: #e1f0e7;
          color: #2b6b4b;
          font-weight: 600;
          font-size: 14px;
        }
        .intro-av {
          width: 42px;
          height: 42px;
          border-radius: 50%;
          background: #2f62d8;
          color: #fff;
          display: grid;
          place-items: center;
          font-weight: 700;
          font-size: 15px;
        }
        .intro-head h2 {
          font-size: clamp(44px, 5.5vw, 76px);
          font-weight: 800;
          letter-spacing: -0.05em;
          line-height: 1;
          color: #10261c;
        }
        .intro-head p {
          color: #5d7468;
          margin-top: 8px;
          font-size: 17px;
        }
        .intro-status {
          padding: 16px 28px;
          border-radius: 99px;
          background: rgba(255, 255, 255, 0.75);
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          font-weight: 600;
          display: flex;
          gap: 30px;
          flex-wrap: wrap;
          font-size: 14px;
          box-shadow: 0 10px 30px rgba(30, 70, 50, 0.05);
        }
        .intro-status em {
          font-weight: 600;
          font-size: 12px;
          letter-spacing: 0.18em;
          color: #5d7468;
          margin-right: 10px;
          font-style: normal;
        }
        .intro-cards {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
        }
        .intro-card {
          background: #fff;
          border-radius: 34px;
          padding: 26px 24px;
          box-shadow: 0 22px 50px rgba(30, 70, 50, 0.1);
          will-change: transform, filter, opacity;
          min-height: 220px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }
        .intro-card.dk {
          background: linear-gradient(160deg, #1d4d38, #2f6b52);
          color: #fff;
        }
        .intro-card h6 {
          font-weight: 600;
          font-size: 11px;
          letter-spacing: 0.2em;
          text-transform: uppercase;
          color: #5d7468;
          line-height: 1.5;
        }
        .intro-card.dk h6 {
          color: rgba(255, 255, 255, 0.75);
        }
        .intro-card strong {
          display: block;
          font-size: clamp(30px, 3.2vw, 46px);
          letter-spacing: -0.04em;
          margin: 18px 0 8px;
          font-weight: 800;
          line-height: 1;
        }
        .intro-card strong small {
          font-size: 0.5em;
          letter-spacing: 0;
          font-weight: 600;
          margin-left: 2px;
        }
        .intro-card .d {
          display: flex;
          gap: 8px;
          align-items: center;
          font-size: 13px;
          color: #5d7468;
          flex-wrap: wrap;
        }
        .intro-card.dk .d {
          color: rgba(255, 255, 255, 0.85);
        }
        .intro-card .d b {
          padding: 3px 10px;
          border-radius: 99px;
          background: #e1f0e7;
          color: #2b6b4b;
          font-size: 12px;
        }
        .intro-card.dk .d b {
          background: rgba(255, 255, 255, 0.2);
          color: #fff;
        }
        .intro-card p {
          margin-top: 6px;
          font-weight: 600;
          font-size: 12.5px;
        }
        .intro-hero {
          position: absolute;
          inset: 0;
          display: grid;
          place-items: center;
          text-align: center;
          padding: 24px;
          pointer-events: none;
          will-change: opacity, filter, transform;
          z-index: 20;
        }
        .intro-hero > div {
          position: relative;
        }
        .intro-hero > div::before {
          content: "";
          position: absolute;
          inset: -20% -30%;
          background: radial-gradient(closest-side, rgba(240, 246, 243, 0.95), rgba(240, 246, 243, 0));
          z-index: -1;
        }
        .intro-pill {
          display: inline-flex;
          gap: 12px;
          align-items: center;
          padding: 8px 24px 8px 8px;
          border-radius: 99px;
          background: #fff;
          box-shadow: 0 14px 34px rgba(30, 70, 50, 0.12);
          margin-bottom: 24px;
          text-align: left;
        }
        .intro-pill i {
          width: 44px;
          height: 44px;
          border-radius: 50%;
          background: linear-gradient(135deg, #1b4a35, #348060);
          display: grid;
          place-items: center;
          box-shadow: 0 8px 20px rgba(27, 74, 53, 0.3);
        }
        .intro-pill b {
          display: block;
          font-size: 16px;
          font-weight: 800;
          color: #10261c;
        }
        .intro-pill small {
          color: #2b6b4b;
          font-weight: 700;
          font-size: 11px;
          letter-spacing: 0.12em;
        }
        .intro-hero h1 {
          font-weight: 800;
          font-size: clamp(46px, 9vw, 120px);
          line-height: 0.95;
          letter-spacing: -0.055em;
          color: #10261c;
          filter: blur(24px);
          opacity: 0;
          transform: translateY(30px) scale(1.06);
          transition: filter 1.8s cubic-bezier(0.2, 0.7, 0.1, 1), opacity 1.5s, transform 1.8s cubic-bezier(0.2, 0.7, 0.1, 1);
        }
        .intro-sub {
          margin-top: 20px;
          font-size: clamp(16px, 1.8vw, 22px);
          color: #5d7468;
          opacity: 0;
          filter: blur(10px);
          transition: opacity 1.4s 0.7s, filter 1.4s 0.7s;
        }
        .intro-hint {
          position: absolute;
          bottom: 5vh;
          left: 0;
          right: 0;
          display: grid;
          justify-items: center;
          gap: 10px;
          font-weight: 700;
          font-size: 11px;
          letter-spacing: 0.22em;
          color: #5d7468;
          opacity: 0;
          transition: opacity 1s 1.4s;
        }
        .intro-mouse {
          width: 24px;
          height: 38px;
          border: 2px solid #5d7468;
          border-radius: 14px;
          position: relative;
        }
        .intro-mouse::after {
          content: "";
          position: absolute;
          left: 50%;
          top: 7px;
          width: 4px;
          height: 7px;
          margin-left: -2px;
          border-radius: 2px;
          background: #2b6b4b;
          animation: mouseBob 1.6s infinite;
        }
        @keyframes mouseBob {
          to {
            transform: translateY(12px);
            opacity: 0;
          }
        }
        .ready .intro-hero h1 {
          filter: none;
          opacity: 1;
          transform: none;
        }
        .ready .intro-sub {
          opacity: 1;
          filter: none;
        }
        .ready .intro-hint {
          opacity: 1;
        }
        .intro-skip {
          position: fixed;
          top: calc(22px + env(safe-area-inset-top, 0px));
          right: 24px;
          z-index: 120;
          padding: 11px 22px;
          border-radius: 99px;
          border: 1.5px solid #1b4a35;
          background: rgba(255, 255, 255, 0.75);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          color: #1b4a35;
          font-weight: 700;
          font-size: 13.5px;
          cursor: pointer;
          box-shadow: 0 8px 24px rgba(27, 74, 53, 0.15);
          transition: background 0.2s, transform 0.15s;
        }
        .intro-skip:hover {
          background: rgba(255, 255, 255, 0.95);
          transform: translateY(-1px);
        }
        .intro-skip:focus-visible {
          outline: 3px solid #348060;
          outline-offset: 3px;
        }
        @media (max-width: 980px) {
          .intro-app {
            grid-template-columns: 1fr;
            padding: 16px;
          }
          .intro-side {
            display: none;
          }
          .intro-cards {
            grid-template-columns: repeat(2, 1fr);
          }
          .intro-status {
            display: none;
          }
        }
        @media (max-width: 520px) {
          .intro-cards {
            grid-template-columns: 1fr;
          }
          .intro-card {
            min-height: 0;
          }
        }
      `}</style>
    </div>
  );
};

export default CinematicIntro;

