import React, { useRef, useEffect, useState, ReactNode } from 'react';

export interface ScrollExpandProps {
  src: string;
  alt?: string;
  title?: string;
  subtitle?: string;
  scrollHint?: string;
  useWindowScroll?: boolean;
  mediaZoom?: number;
  onSkip?: () => void;
  onComplete?: () => void;
  children?: ReactNode;
}

export const ScrollExpand: React.FC<ScrollExpandProps> = ({
  src,
  alt = 'Agricultural food security landscape',
  title = 'Every Grain. Accounted For.',
  subtitle = 'Food Security Platform',
  scrollHint = 'Scroll to reveal dashboard',
  mediaZoom = 1.25,
  onSkip,
  children
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mediaQuery.matches);
    const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion) {
      setScrollProgress(1);
      return;
    }

    const handleScroll = () => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      // Scroll distance inside container until it hits the bottom
      const totalDistance = containerRef.current.offsetHeight - window.innerHeight;

      if (totalDistance <= 0) {
        setScrollProgress(1);
        return;
      }

      const scrolled = -rect.top;
      const progress = Math.max(0, Math.min(1, scrolled / totalDistance));
      setScrollProgress(progress);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  }, [prefersReducedMotion]);

  // Interpolations based on progress (0 -> 1)
  // Stage 1 (0 -> 0.35): Center frame with generous surrounding whitespace
  // Stage 2 (0.35 -> 0.85): Smoothly expands to fill 100vw x 100vh, corners flatten
  // Stage 3 (0.85 -> 1.0): Fully open stage, handing over directly to the dashboard

  // Width: from centered ~800px on desktop (min 85vw on mobile) to 100vw
  const widthPct = prefersReducedMotion
    ? 100
    : 54 + 46 * Math.pow(scrollProgress, 1.3);

  // Height: from 58vh to 100vh
  const heightVh = prefersReducedMotion
    ? 100
    : 58 + 42 * Math.pow(scrollProgress, 1.3);

  // Corner radius: 36px down to 0px
  const borderRadius = prefersReducedMotion
    ? 0
    : Math.max(0, 36 * (1 - Math.pow(scrollProgress, 1.4)));

  // Image zoom scale: starts at 1.0 -> mediaZoom
  const imageScale = 1.0 + (mediaZoom - 1.0) * scrollProgress;

  // Text opacity: fully visible, begins fading smoothly as expansion reaches full stage
  const textOpacity = prefersReducedMotion
    ? 0
    : Math.max(0, 1 - Math.pow(scrollProgress / 0.72, 2.5));

  const textTranslateY = -scrollProgress * 55;

  // Overlay opacity ensures clear white text contrast at all scroll positions
  const overlayOpacity = 0.52 + 0.28 * scrollProgress;

  // Scroll hint fades out within the first 25% of scroll
  const hintOpacity = Math.max(0, 1 - scrollProgress * 4.0);

  return (
    <div
      ref={containerRef}
      className="scroll-expand-section"
      style={{
        position: 'relative',
        width: '100vw',
        height: '240vh', // Generous smooth scroll runway
        background: '#062d22',
        zIndex: 50,
        margin: 0,
        padding: 0
      }}
    >
      {/* Sticky Fullscreen Pinned Viewport */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          background: '#062d22'
        }}
      >
        {/* Skip Intro Button */}
        {onSkip && scrollProgress < 0.92 && (
          <button
            type="button"
            onClick={onSkip}
            aria-label="Skip introduction and proceed to dashboard"
            style={{
              position: 'absolute',
              top: '28px',
              right: '32px',
              zIndex: 60,
              padding: '9px 18px',
              borderRadius: '999px',
              background: 'rgba(255, 255, 255, 0.16)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.28)',
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: 700,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              cursor: 'pointer',
              transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.3)';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.16)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            Skip Intro →
          </button>
        )}

        {/* Centered Media Frame that expands on scroll */}
        <div
          className="media-frame"
          style={{
            position: 'relative',
            width: `${widthPct}vw`,
            height: `${heightVh}vh`,
            maxWidth: scrollProgress > 0.88 ? '100vw' : '1360px',
            borderRadius: `${borderRadius}px`,
            overflow: 'hidden',
            boxShadow: scrollProgress > 0.85
              ? 'none'
              : '0 36px 80px -15px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            willChange: 'width, height, border-radius'
          }}
        >
          {/* Background Hero Image */}
          <img
            src={src}
            alt={alt}
            style={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              objectPosition: 'center 45%',
              transform: `scale(${imageScale})`,
              transformOrigin: 'center center',
              transition: 'transform 0.08s linear',
              willChange: 'transform'
            }}
          />

          {/* Dark Forest Green Gradient Overlay for readability */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: `linear-gradient(180deg, rgba(6, 45, 34, ${overlayOpacity * 0.75}) 0%, rgba(8, 26, 20, ${overlayOpacity}) 60%, rgba(4, 16, 12, ${overlayOpacity * 1.15}) 100%)`,
              backdropFilter: scrollProgress < 0.25 ? 'none' : `blur(${scrollProgress * 2}px)`,
              pointerEvents: 'none'
            }}
          />

          {/* Intro Headline & Content */}
          <div
            style={{
              position: 'relative',
              zIndex: 10,
              textAlign: 'center',
              padding: '0 28px',
              maxWidth: '880px',
              color: '#ffffff',
              opacity: textOpacity,
              transform: `translateY(${textTranslateY}px)`,
              transition: 'opacity 0.1s linear, transform 0.1s linear',
              pointerEvents: textOpacity < 0.1 ? 'none' : 'auto'
            }}
          >
            {/* Logo Badge */}
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '12px',
                padding: '7px 18px 7px 8px',
                borderRadius: '999px',
                background: 'rgba(255, 255, 255, 0.12)',
                backdropFilter: 'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
                border: '1px solid rgba(255, 255, 255, 0.25)',
                marginBottom: '24px',
                boxShadow: '0 8px 24px rgba(0, 0, 0, 0.25)'
              }}
            >
              <div
                style={{
                  width: '34px',
                  height: '34px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #064E3B 0%, #10B981 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ffffff'
                }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                  <path d="M12 22v-9" strokeLinecap="round" />
                  <path d="M12 13C12 7.477 7.523 3 2 3c0 5.523 4.477 10 10 10z" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M12 10c0-4.418 3.582-8 8-8 0 4.418-3.582 8-8 8z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div style={{ textAlign: 'left', lineHeight: 1.15 }}>
                <div style={{ fontFamily: 'Bricolage Grotesque, sans-serif', fontSize: '15px', fontWeight: 700, letterSpacing: '-0.01em' }}>
                  RationRight
                </div>
                <div style={{ fontSize: '11px', color: '#7fd8aa', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                  {subtitle}
                </div>
              </div>
            </div>

            {/* Headline */}
            <h1
              style={{
                fontFamily: 'Bricolage Grotesque, sans-serif',
                fontSize: 'clamp(38px, 5.8vw, 70px)',
                fontWeight: 800,
                letterSpacing: '-0.035em',
                lineHeight: 1.08,
                marginBottom: '18px',
                textShadow: '0 4px 20px rgba(0, 0, 0, 0.5)',
                textWrap: 'balance' as any
              }}
            >
              {title}
            </h1>

            {/* Subtext */}
            <p
              style={{
                fontSize: 'clamp(15px, 1.8vw, 19px)',
                fontWeight: 500,
                color: 'rgba(255, 255, 255, 0.92)',
                lineHeight: 1.5,
                maxWidth: '640px',
                margin: '0 auto',
                textShadow: '0 2px 10px rgba(0, 0, 0, 0.4)',
                textWrap: 'balance' as any
              }}
            >
              AI-powered intelligence for transparent ration distribution.
            </p>

            {children && (
              <div style={{ marginTop: '20px' }}>
                {children}
              </div>
            )}
          </div>

          {/* Animated Scroll Indicator */}
          <div
            style={{
              position: 'absolute',
              bottom: '30px',
              left: '50%',
              transform: 'translateX(-50%)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px',
              opacity: hintOpacity,
              transition: 'opacity 0.2s ease',
              pointerEvents: 'none',
              zIndex: 10
            }}
          >
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
                color: 'rgba(255, 255, 255, 0.85)',
                textShadow: '0 2px 6px rgba(0,0,0,0.6)'
              }}
            >
              {scrollHint}
            </span>
            <div
              style={{
                width: '20px',
                height: '32px',
                borderRadius: '12px',
                border: '2px solid rgba(255, 255, 255, 0.65)',
                display: 'flex',
                justifyContent: 'center',
                paddingTop: '6px'
              }}
            >
              <div
                style={{
                  width: '4px',
                  height: '7px',
                  borderRadius: '2px',
                  backgroundColor: '#7fd8aa',
                  animation: 'scrollBob 1.6s ease-in-out infinite'
                }}
              />
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes scrollBob {
          0%, 100% { transform: translateY(0); opacity: 0.9; }
          50% { transform: translateY(8px); opacity: 0.3; }
        }
      `}</style>
    </div>
  );
};

export default ScrollExpand;
