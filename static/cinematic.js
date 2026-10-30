(function() {
  const stage = document.getElementById('stage');
  const hero = document.getElementById('hero');
  const dash = document.getElementById('dashboard');
  const ga = document.getElementById('ga');
  const gb = document.getElementById('gb');
  const skipBtn = document.getElementById('skipBtn');
  const replayBtn = document.getElementById('replayBtn');
  const track = document.getElementById('track');
  const mainScroll = document.getElementById('mainScrollArea');
  const gaugeArc = document.getElementById('gaugeArc');
  const gaugeNumber = document.getElementById('gaugeNumber');

  if (!stage || !dash || !track) return;

  setTimeout(() => stage.classList.add('ready'), 120);

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const seg   = (p, a, b) => clamp((p - a) / (b - a), 0, 1);
  const ease  = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  const enterElements = [...dash.querySelectorAll('[data-enter]')].map(el => {
    const dir = el.dataset.enter;
    const offsets = { left: [-60, 0], top: [0, -24], up: [0, 50] };
    const [dx, dy] = offsets[dir] || [0, 0];
    return {
      el,
      a: parseFloat(el.dataset.start || '0'),
      b: parseFloat(el.dataset.end || '1'),
      dx, dy
    };
  });

  const tableRows = [...dash.querySelectorAll('.t-stagger')].map((el, i) => ({ el, idx: i }));
  const cardElements = [0, 1, 2, 3, 4].map(i => document.getElementById(`card-${i}`));
  const iconElements = cardElements.map(c => c ? c.querySelector('.kpi-icon') : null);

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

  let cardScatterOffsets = [];

  function measureFLIP() {
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
  }

  measureFLIP();
  window.addEventListener('resize', measureFLIP, { passive: true });
  if (document.fonts) document.fonts.ready.then(measureFLIP);

  cardElements.forEach(card => {
    if (!card) return;
    card.addEventListener('mouseenter', () => card.classList.add('is-hovered'));
    card.addEventListener('mouseleave', () => card.classList.remove('is-hovered'));
  });

  let cur = 0;
  let target = 0;

  function maxScroll() {
    return Math.max(1, track.offsetHeight - window.innerHeight);
  }

  function handleScroll() {
    target = clamp(window.scrollY / maxScroll(), 0, 1);
  }

  window.addEventListener('scroll', handleScroll, { passive: true });
  handleScroll();

  if (reduce) cur = target;

  function render(p, time = 0) {
    // 1. Hero text push-through and blur away
    const h = ease(seg(p, 0.05, 0.42));
    if (hero) {
      hero.style.opacity = (1 - h);
      hero.style.filter = h > 0.01 ? `blur(${h * 28}px)` : 'none';
      hero.style.transform = `scale(${1 + h * 0.35})`;
      hero.style.pointerEvents = 'none';
    }

    if (ga) ga.style.transform = `translate(${p * 14}vw, ${p * 10}vh)`;
    if (gb) gb.style.transform = `translate(${-p * 12}vw, ${-p * 8}vh)`;

    if (skipBtn) {
      skipBtn.style.opacity = (1 - seg(p, 0.45, 0.70));
      skipBtn.style.pointerEvents = p > 0.65 ? 'none' : 'auto';
    }
    if (replayBtn) {
      const rp = ease(seg(p, 0.90, 1.0));
      replayBtn.style.opacity = rp;
      replayBtn.style.pointerEvents = rp > 0.5 ? 'auto' : 'none';
    }

    // 2. Camera push on whole dashboard
    if (dash) {
      const cam = 1.04 - 0.04 * ease(seg(p, 0.48, 0.95));
      dash.style.transform = `scale(${cam})`;
    }

    // 3. FLIP: 5 Scattered Cards converge smoothly into the final dashboard grid
    const convP = ease(seg(p, 0.12, 0.78));

    cardElements.forEach((card, i) => {
      if (!card) return;
      const scatter = cardScatterOffsets[i] || { initDx: 0, initDy: 0, initRot: 0, initScale: 1, initBlur: 0 };

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
        card.style.opacity = curOpacity;
        card.style.pointerEvents = 'none';
        card.classList.remove('is-hovered');
      }
    });

    const iconP = ease(seg(p, 0.68, 0.82));
    iconElements.forEach(ic => {
      if (ic) ic.style.opacity = iconP;
    });

    // 4. Enter elements
    enterElements.forEach(({ el, a, b, dx, dy }) => {
      const q = ease(seg(p, a, b));
      el.style.opacity = q;
      el.style.filter = q >= 0.999 ? '' : `blur(${(1 - q) * 18}px)`;
      el.style.transform = q >= 0.999 ? '' : `translate(${dx * (1 - q)}px, ${dy * (1 - q)}px)`;
      el.style.pointerEvents = q > 0.75 ? 'auto' : 'none';
    });

    // 5. Table rows stagger
    tableRows.forEach(({ el, idx }) => {
      const rowStart = 0.76 + idx * 0.05;
      const rowEnd = rowStart + 0.12;
      const rq = ease(seg(p, rowStart, rowEnd));
      el.style.opacity = rq;
      el.style.filter = rq >= 0.999 ? '' : `blur(${(1 - rq) * 12}px)`;
      el.style.transform = rq >= 0.999 ? '' : `translateY(${(1 - rq) * 16}px)`;
    });

    // 6. Gauge
    const covP = ease(seg(p, 0.80, 0.98));
    if (gaugeArc) {
      gaugeArc.style.strokeDashoffset = 330 * (1 - 0.952 * covP);
    }
    if (gaugeNumber) {
      gaugeNumber.textContent = `${(95.2 * covP).toFixed(1)}%`;
    }

    // 7. Main scrollable area (keep visible during intro so floating cards are never clipped)
    if (mainScroll) {
      if (p >= 0.96) {
        mainScroll.style.overflowY = 'auto';
        mainScroll.style.overflowX = 'hidden';
      } else {
        mainScroll.style.overflow = 'visible';
        mainScroll.scrollTop = 0;
      }
    }
  }

  function loop(timestamp) {
    const time = (timestamp || performance.now()) * 0.0015;
    cur += (target - cur) * (reduce ? 1 : 0.07);
    if (Math.abs(target - cur) < 0.0002) cur = target;
    render(cur, time);
    requestAnimationFrame(loop);
  }

  requestAnimationFrame(loop);

  if (skipBtn) {
    skipBtn.addEventListener('click', () => {
      window.scrollTo({ top: maxScroll(), behavior: 'smooth' });
    });
  }
  if (replayBtn) {
    replayBtn.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }
})();
