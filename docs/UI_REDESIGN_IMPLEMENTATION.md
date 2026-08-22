# RationRight UI Redesign — Implementation Guide

## Overview

This guide provides the exact CSS and HTML changes needed to transform RationRight from a "feature-heavy AI dashboard" into a "simple enterprise investigation workspace."

**Target aesthetic:** Clean, minimal, professional — inspired by the Dribbble "Minimal Pending Orders Table" reference.

---

## Phase 1: CSS Variable Refinement

### File: `static/styles.css`

Replace the `:root` section with refined values:

```css
:root {
  /* Primary — keep existing green */
  --forest: #14532D;
  --forest-2: #166534;
  --emerald: #059669;
  --emerald-bright: #10B981;
  
  /* Secondary */
  --soft-green: #ECFDF5;
  --pale-green: #F0FDF4;
  
  /* Neutral — lighter, cleaner */
  --bg: #F9FAFB;
  --card: #FFFFFF;
  --text: #111827;
  --text-2: #6B7280;
  --text-3: #9CA3AF;
  --border: #E5E7EB;
  --border-2: #D1D5DB;
  
  /* Status */
  --success: #059669;
  --warning: #D97706;
  --error: #DC2626;
  --info: #2563EB;
  --amber: #D97706;
  
  /* Status surfaces */
  --surface-critical: #FEF2F2;
  --surface-critical-soft: #FEF2F2;
  --border-critical: #FECACA;
  --surface-warning: #FFFBEB;
  --border-warning: #FDE68A;
  --surface-info: #EFF6FF;
  --border-info: #BFDBFE;
  --border-success: #A7F3D0;
  --border-success-soft: #D1FAE5;
  --text-critical: #7F1D1D;
  --text-warning: #92400E;
  --text-info: #1E40AF;
  
  /* Shape — tighter */
  --radius-sm: 6px;
  --radius: 8px;
  --radius-lg: 10px;
  --radius-xl: 12px;
  
  /* Shadows — minimal */
  --shadow-xs: 0 1px 2px rgba(0, 0, 0, .04);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, .06);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, .08);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, .12);
  
  /* Type */
  --font: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  
  /* Layout */
  --sidebar-w: 220px;
  --sidebar-w-collapsed: 220px; /* no collapse */
  --topbar-h: 52px;
  
  /* Focus */
  --focus-ring: var(--emerald-bright);
}
```

---

## Phase 2: Sidebar Refinement

### Changes:

1. **Remove collapse functionality** — keep sidebar always expanded
2. **Reduce width** from 252px to 220px
3. **Tighten padding and spacing**
4. **Simplify brand area**

### CSS Updates:

```css
/* Sidebar — refined */
.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: 220px; /* was 252px */
  z-index: 40;
  display: flex;
  flex-direction: column;
  background: var(--card);
  border-right: 1px solid var(--border);
}

/* Remove collapse button */
.sidebar-collapse {
  display: none !important;
}

/* Brand area — simpler */
.sidebar-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 14px 12px;
}

.brand-mark {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: #fff;
  background: var(--forest);
}

.brand-text strong {
  font-size: 14px;
  letter-spacing: .1px;
}

.brand-text small {
  font-size: 10px;
  color: var(--text-2);
}

/* Nav sections */
.nav-section {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .8px;
  text-transform: uppercase;
  color: var(--text-3);
  padding: 12px 12px 4px;
}

/* Nav items — tighter */
.nav a {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 12px;
  border-radius: var(--radius-sm);
  color: var(--text-2);
  font-weight: 500;
  font-size: 13px;
  white-space: nowrap;
}

.nav a:hover {
  background: var(--bg);
  color: var(--text);
}

.nav a.is-active {
  background: var(--pale-green);
  color: var(--forest);
  font-weight: 600;
}

/* Active indicator */
.nav a.is-active::before {
  content: "";
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 3px;
  background: var(--emerald);
}

/* Nav icons — slightly smaller */
.nav-icon {
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
}

.nav-icon svg {
  width: 18px;
  height: 18px;
}

/* Alert count badge */
.nav-count {
  margin-left: auto;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: var(--error);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}

/* Sidebar footer */
.sidebar-foot {
  padding: 10px;
  border-top: 1px solid var(--border);
}

.profile-mini {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
}

.avatar {
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: #fff;
  font-weight: 700;
  font-size: 12px;
  background: var(--forest);
}

.profile-mini-text strong {
  font-size: 12px;
}

.profile-mini-text small {
  font-size: 10px;
  color: var(--text-2);
}
```

---

## Phase 3: Top Header Simplification

### Changes:

1. **Reduce height** from 60px to 52px
2. **Remove backdrop blur**
3. **Simplify search trigger**
4. **Reduce profile to avatar only**

### CSS Updates:

```css
/* Topbar — simpler */
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  height: 52px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  background: var(--card);
  border-bottom: 1px solid var(--border);
  /* No backdrop-filter */
}

/* Breadcrumb */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.crumb-root {
  color: var(--text-2);
  font-weight: 500;
}

.crumb-sep {
  color: var(--text-3);
}

.crumb-current {
  font-weight: 600;
  color: var(--text);
}

/* Search trigger — minimal */
.search-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-3);
  background: var(--card);
  min-width: 160px;
  font-size: 13px;
}

.search-trigger:hover {
  border-color: var(--border-2);
  color: var(--text-2);
}

.search-text {
  flex: 1;
  text-align: left;
}

/* Profile button — avatar only */
.profile-btn {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 4px;
  border-radius: 50%;
}

.profile-btn:hover {
  background: var(--bg);
}

.profile-btn-text {
  display: none; /* hide name on desktop */
}

/* Data status chip — smaller */
.data-status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--card);
  color: var(--text-2);
  font-size: 11px;
  font-weight: 600;
}

.data-status-chip .status-dot {
  width: 6px;
  height: 6px;
}

/* Icon buttons */
.icon-btn {
  position: relative;
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  color: var(--text-2);
  border-radius: var(--radius-sm);
}

.icon-btn:hover {
  background: var(--bg);
  color: var(--text);
}
```

---

## Phase 4: Button Refinement

### CSS Updates:

```css
/* Buttons — compact */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 32px;
  padding: 0 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 600;
  border: 1px solid transparent;
  transition: all 150ms ease;
}

.btn:active {
  transform: translateY(1px);
}

.btn-primary {
  background: var(--forest);
  color: #fff;
}

.btn-primary:hover {
  background: var(--forest-2);
}

.btn-primary:disabled {
  background: var(--border-2);
  color: #fff;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--card);
  border-color: var(--border);
  color: var(--text);
}

.btn-secondary:hover {
  border-color: var(--border-2);
  background: var(--bg);
}

.btn-ghost {
  background: transparent;
  color: var(--text-2);
}

.btn-ghost:hover {
  background: var(--bg);
  color: var(--text);
}

.btn-sm {
  height: 28px;
  padding: 0 10px;
  font-size: 12px;
}
```

---

## Phase 5: Badge Refinement

### CSS Updates:

```css
/* Badges — refined */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid transparent;
  white-space: nowrap;
}

/* Remove dot indicator by default */
.badge .dot {
  display: none;
}

/* Severity variants */
.badge.critical {
  color: #991B1B;
  background: #FEF2F2;
}

.badge.high {
  color: #991B1B;
  background: #FEF2F2;
}

.badge.medium {
  color: #92400E;
  background: #FFFBEB;
}

.badge.low {
  color: #065F46;
  background: #ECFDF5;
}

.badge.info {
  color: #1E40AF;
  background: #EFF6FF;
}

.badge.success {
  color: #065F46;
  background: #ECFDF5;
}

.badge.neutral {
  color: #374151;
  background: #F3F4F6;
  border-color: var(--border);
}

/* Priority chips */
.priority-chip {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .5px;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 999px;
}

.priority-chip.critical {
  color: #991B1B;
  background: #FEF2F2;
}

.priority-chip.high {
  color: #991B1B;
  background: #FEF2F2;
}

.priority-chip.medium {
  color: #92400E;
  background: #FFFBEB;
}

.priority-chip.low {
  color: #065F46;
  background: #ECFDF5;
}
```

---

## Phase 6: Table Refinement

### CSS Updates:

```css
/* Tables — clean */
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

table.data {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  background: var(--card);
}

table.data thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--bg);
  color: var(--text-2);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .5px;
  text-transform: uppercase;
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

table.data tbody td {
  padding: 10px 12px;
  border-bottom: 1px solid #F3F4F6;
  vertical-align: middle;
  white-space: nowrap;
}

table.data tbody tr:last-child td {
  border-bottom: 0;
}

table.data tbody tr {
  transition: background 150ms ease;
}

table.data tbody tr:hover {
  background: #F9FAFB;
}

table.data .mono {
  font-family: var(--mono);
  font-size: 12px;
}

table.data .num {
  font-variant-numeric: tabular-nums;
  text-align: right;
}

table.data .row-click {
  cursor: pointer;
}

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-2);
}

.pagination button {
  min-width: 28px;
  height: 28px;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  font-weight: 600;
  font-size: 12px;
}

.pagination button:hover:not(:disabled) {
  background: var(--bg);
}

.pagination button.is-active {
  background: var(--forest);
  color: #fff;
}

.pagination button:disabled {
  color: var(--text-3);
  cursor: not-allowed;
}
```

---

## Phase 7: Card Refinement

### CSS Updates:

```css
/* Cards — minimal */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  /* No default shadow */
}

.card.hoverable:hover {
  border-color: var(--border-2);
  box-shadow: var(--shadow-sm);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #F3F4F6;
}

.card-head h3 {
  font-size: 13px;
  font-weight: 600;
}

.card-body {
  padding: 16px;
}

/* KPI cards — compact */
.kpi {
  position: relative;
  overflow: hidden;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
}

.kpi .kpi-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.kpi .kpi-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-2);
  text-transform: uppercase;
  letter-spacing: .5px;
}

.kpi .kpi-icon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  color: var(--emerald);
  background: var(--pale-green);
}

.kpi .kpi-value {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -.3px;
  margin-top: 8px;
  font-variant-numeric: tabular-nums;
}

.kpi .kpi-sub {
  font-size: 11px;
  color: var(--text-3);
  margin-top: 2px;
}

.kpi .kpi-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 999px;
  margin-top: 6px;
}
```

---

## Phase 8: Form Input Refinement

### CSS Updates:

```css
/* Inputs — compact */
.input,
.select {
  height: 32px;
  padding: 0 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--card);
  font-size: 13px;
}

.input:focus,
.select:focus {
  outline: none;
  border-color: var(--emerald-bright);
  box-shadow: 0 0 0 3px rgba(16, 185, 129, .12);
}

.input::placeholder {
  color: var(--text-3);
}

.select {
  padding-right: 28px;
  appearance: none;
  background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236B7280' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
}

/* Filter row */
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
```

---

## Phase 9: Page Content Simplification

### View/Content Updates:

```css
/* View — refined */
.view {
  flex: 1;
  padding: 20px 24px 40px;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
}

.view-head {
  margin-bottom: 16px;
}

.view-head h1 {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -.2px;
}

.view-head p {
  color: var(--text-2);
  margin-top: 4px;
  max-width: 640px;
  font-size: 13px;
}

.section {
  margin-top: 20px;
}

.section-title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .6px;
  text-transform: uppercase;
  color: var(--text-3);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title .hint {
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0;
  color: var(--text-3);
  font-size: 11px;
}

/* Grid — tighter */
.grid {
  display: grid;
  gap: 12px;
}

.grid.kpi-grid {
  grid-template-columns: repeat(4, 1fr);
}

.grid.cols-2 {
  grid-template-columns: repeat(2, 1fr);
}

.grid.cols-3 {
  grid-template-columns: repeat(3, 1fr);
}

.grid.cols-4 {
  grid-template-columns: repeat(4, 1fr);
}
```

---

## Phase 10: Remove Unnecessary Visual Effects

### Remove or Simplify:

1. **Remove gradient backgrounds** from alert cards
2. **Remove excessive shadows** — use only `--shadow-xs` or `--shadow-sm`
3. **Remove animations** — keep only essential transitions
4. **Remove decorative icons** — use only functional icons
5. **Remove gradient badges** — use solid colors

### CSS Updates:

```css
/* Alert card — simplified */
.alert-card {
  border: 1px solid var(--border);
  border-left: 3px solid var(--emerald);
  border-radius: var(--radius);
  background: var(--card);
  /* No gradient, no shadow */
}

.alert-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  /* No gradient background */
}

.alert-head .kicker {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .6px;
  text-transform: uppercase;
  color: var(--emerald);
}

.alert-head .alert-message {
  margin-top: 4px;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text);
}

/* AI card — simplified */
.ai-card {
  position: relative;
  overflow: hidden;
  /* No gradient top bar */
}

.ai-card .ai-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.ai-card .ai-icon {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  color: var(--emerald);
  background: var(--pale-green);
}

.ai-card .ai-title {
  font-weight: 600;
  font-size: 13px;
}

.ai-card .ai-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
}

/* Trace chain — simplified */
.trace-chain {
  display: flex;
  align-items: stretch;
  flex-wrap: wrap;
  gap: 6px;
}

.trace-node {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
  min-width: 80px;
}

.trace-id {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--forest);
}

.trace-label {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .5px;
  text-transform: uppercase;
  color: var(--text-3);
}
```

---

## Phase 11: Responsive Refinement

### CSS Updates:

```css
/* Responsive */
@media (max-width: 1280px) {
  .grid.kpi-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 1024px) {
  .grid.cols-4,
  .grid.cols-5 {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 860px) {
  .sidebar {
    transform: translateX(-100%);
    width: 220px;
    box-shadow: var(--shadow-lg);
  }
  
  .main,
  .app.is-collapsed .main {
    margin-left: 0;
  }
  
  .nav-toggle {
    display: grid;
  }
  
  .search-text,
  .search-trigger kbd {
    display: none;
  }
  
  .search-trigger {
    min-width: 32px;
    width: 32px;
    padding: 0;
    justify-content: center;
  }
  
  .profile-btn-text {
    display: none;
  }
  
  .view {
    padding: 16px 16px 96px;
  }
  
  .bottom-nav {
    display: flex;
  }
  
  .grid.cols-2,
  .grid.cols-3 {
    grid-template-columns: 1fr;
  }
  
  .grid.kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 520px) {
  .grid.kpi-grid {
    grid-template-columns: 1fr;
  }
  
  .topbar {
    padding: 0 12px;
  }
  
  .view-head h1 {
    font-size: 18px;
  }
}
```

---

## Phase 12: Remove Collapse Functionality

### HTML Updates:

1. **Remove sidebar collapse button** from `index.html`
2. **Remove collapse-related JavaScript** from `app.js`
3. **Keep sidebar always expanded**

### HTML Changes:

```html
<!-- Remove this button -->
<button class="sidebar-collapse" id="sidebar-collapse" type="button" aria-label="Collapse sidebar" aria-expanded="true">
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
</button>
```

### JavaScript Changes:

Remove or comment out:
- Collapse toggle event listener
- `is-collapsed` class toggling
- Sidebar width transitions

---

## Implementation Order

1. **Phase 1:** CSS Variables (10 minutes)
2. **Phase 2:** Sidebar (15 minutes)
3. **Phase 3:** Top Header (10 minutes)
4. **Phase 4:** Buttons (5 minutes)
5. **Phase 5:** Badges (5 minutes)
6. **Phase 6:** Tables (10 minutes)
7. **Phase 7:** Cards (10 minutes)
8. **Phase 8:** Forms (5 minutes)
9. **Phase 9:** Page Content (10 minutes)
10. **Phase 10:** Remove Effects (10 minutes)
11. **Phase 11:** Responsive (10 minutes)
12. **Phase 12:** Remove Collapse (5 minutes)

**Total estimated time:** ~1.5 hours

---

## Testing Checklist

After each phase, verify:

- [ ] All pages render correctly
- [ ] Navigation works
- [ ] Tables display properly
- [ ] Badges show correct colors
- [ ] Buttons function correctly
- [ ] Filters work
- [ ] Responsive layout works
- [ ] Mobile bottom nav works
- [ ] Search works
- [ ] Dropdowns work

After all phases, verify:

- [ ] All API calls work
- [ ] Agent workflow displays
- [ ] Investigation cases open
- [ ] Evidence tables show
- [ ] Reports generate
- [ ] No console errors
- [ ] No broken layouts
- [ ] Performance is acceptable
