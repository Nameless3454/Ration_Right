import React from 'react';

interface TopNavbarProps {
  searchQuery: string;
  onSearchChange: (val: string) => void;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({
  searchQuery,
  onSearchChange
}) => {
  return (
    <div className="top-bar fade-up-card delay-2">
      <div className="search-box">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <circle cx="11" cy="11" r="8" strokeLinecap="round" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" strokeLinecap="round" />
        </svg>
        <input 
          type="text" 
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search cases, FPS centers, beneficiaries..." 
          aria-label="Search cases, FPS centers, beneficiaries" 
        />
      </div>
      
      <div className="top-actions">
        <div className="pill-badge green">
          <span className="dot-pulse"></span>
          <span>Data recent</span>
        </div>

        <button 
          className="icon-btn" 
          aria-label="View notifications" 
          type="button"
          onClick={() => alert('Notifications:\n• Anomaly detected at BENX1 (9 Aug 2026)\n• 12 Low-stock FPS centers require stock replenishment')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" strokeLinecap="round" />
          </svg>
          <span className="badge-dot"></span>
        </button>

        <div className="top-user-group">
          <div className="top-user-avatar">A</div>
          <div className="top-user-meta">
            <span className="name">Admin</span>
            <span className="role">Operator</span>
          </div>
        </div>
      </div>
    </div>
  );
};
