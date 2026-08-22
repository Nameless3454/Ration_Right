# RationRight UI Redesign Specification

## Design Philosophy

Transform RationRight from a "feature-heavy AI dashboard" into a **"simple enterprise investigation workspace"** — calm, professional, evidence-focused, immediately understandable.

**Inspiration reference:** The Dribbble "Minimal Pending Orders Table" — clean white surfaces, narrow sidebar, restrained badges, generous whitespace, clear information hierarchy.

---

## 1. Visual System

### 1.1 Color Palette

```css
:root {
  /* Primary — keep existing green, just refine */
  --forest: #14532D;
  --forest-2: #166534;
  --emerald: #059669;
  --emerald-bright: #10B981;
  
  /* Surfaces — lighter, cleaner */
  --bg: #F9FAFB;           /* page background — very light gray */
  --card: #FFFFFF;          /* content surfaces — pure white */
  --text: #111827;          /* primary text — near black */
  --text-2: #6B7280;        /* secondary text */
  --text-3: #9CA3AF;        /* tertiary/muted text */
  --border: #E5E7EB;        /* subtle borders */
  --border-2: #D1D5DB;      /* slightly stronger border */
  
  /* Status — keep existing semantic colors */
  --success: #059669;
  --warning: #D97706;
  --error: #DC2626;
  --info: #2563EB;
  
  /* Surfaces for status */
  --soft-green: #ECFDF5;
  --pale-green: #F0FDF4;
  --surface-critical: #FEF2F2;
  --surface-warning: #FFFBEB;
  --surface-info: #EFF6FF;
  
  /* Shape — tighter, more professional */
  --radius-sm: 6px;
  --radius: 8px;
  --radius-lg: 10px;
  --radius-pill: 999px;
  
  /* Shadows — minimal */
  --shadow-xs: 0 1px 2px rgba(0, 0, 0, .04);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, .06);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, .08);
  
  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  
  /* Layout */
  --sidebar-w: 220px;       /* narrower than current 252px */
  --topbar-h: 52px;         /* shorter than current 60px */
  
  /* Typography */
  --font: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
```

### 1.2 Typography Scale

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| Page title (h1) | 20px | 700 | --text |
| Section title | 11px | 700 | --text-3 (uppercase, letter-spaced) |
| Card/table header | 13px | 600 | --text |
| Body text | 13px | 400 | --text |
| Caption/meta | 12px | 500 | --text-2 |
| Badge text | 11px | 600 | (varies) |
| Nav label | 13px | 500 | --text-2 |
| Nav active | 13px | 600 | --forest |

### 1.3 Spacing Rules

- **Page padding:** 24px horizontal, 20px vertical
- **Section gap:** 24px between sections
- **Card internal padding:** 16px
- **Table cell padding:** 10px 12px
- **Badge padding:** 2px 8px
- **Button height:** 32px (small) / 36px (default)
- **Input height:** 32px
- **Sidebar item padding:** 7px 12px

---

## 2. Component Specifications

### 2.1 Sidebar (220px wide)

```
┌─────────────────────────────┐
│ [leaf icon] RationRight     │
│             Food Security   │
│─────────────────────────────│
│ OVERVIEW                    │
│   Command Center            │
│   Overview                  │
│─────────────────────────────│
│ DATA                        │
│   Beneficiaries             │
│   Ration Distribution       │
│   Inventory                 │
│   Import Data               │
│   Data Sources              │
│─────────────────────────────│
│ INTELLIGENCE                │
│   AI Analysis               │
│   Analytics                 │
│   AI Insights               │
│   Alerts            (3)     │
│   Decision Support          │
│─────────────────────────────│
│ REPORTING                   │
│   Reports                   │
│─────────────────────────────│
│ SYSTEM                      │
│   Settings                  │
│                             │
│─────────────────────────────│
│ [A] Admin                   │
│   Operator                  │
└─────────────────────────────┘
```

**Rules:**
- Brand: icon + name on one line, subtitle below in gray
- Section headers: 10px uppercase, gray, 8px padding-top
- Nav items: 13px, 500 weight, 7px vertical padding, 6px border-radius
- Active item: left 3px green bar, green background tint, 600 weight
- Alert count badge: small red pill, right-aligned
- Profile: avatar + name + role at bottom, separated by border
- No collapse button — always 220px

### 2.2 Top Header (52px)

```
┌──────────────────────────────────────────────────────────────────────┐
│ [≡]  RationRight / AI Analysis    Search... ⌘K   ● Data fresh  🔔  👤 │
└──────────────────────────────────────────────────────────────────────┘
```

**Rules:**
- Height: 52px
- Background: white with bottom border only (no blur)
- Breadcrumb: "RationRight" in gray, "/" separator, current page in dark
- Search trigger: minimal, just input-style with placeholder
- Data status: small dot + text (no large chip)
- Notifications: simple bell icon with optional red dot
- Profile: small avatar only (no name visible)

### 2.3 Buttons

```css
/* Primary */
.btn-primary {
  height: 32px;
  padding: 0 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  background: #14532D;
  color: white;
}

/* Secondary */
.btn-secondary {
  height: 32px;
  padding: 0 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  background: white;
  border: 1px solid #E5E7EB;
  color: #111827;
}

/* Ghost */
.btn-ghost {
  height: 32px;
  padding: 0 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  background: transparent;
  color: #6B7280;
}
```

### 2.4 Badges/Status Pills

```css
/* All badges use this base */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

/* Severity variants */
.badge.critical { color: #991B1B; background: #FEF2F2; }
.badge.high     { color: #991B1B; background: #FEF2F2; }
.badge.medium   { color: #92400E; background: #FFFBEB; }
.badge.low      { color: #065F46; background: #ECFDF5; }
.badge.info     { color: #1E40AF; background: #EFF6FF; }
.badge.success  { color: #065F46; background: #ECFDF5; }
.badge.neutral  { color: #374151; background: #F3F4F6; }
```

### 2.5 Tables

```css
table.data {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

/* Header */
table.data thead th {
  background: #F9FAFB;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #6B7280;
  padding: 8px 12px;
  border-bottom: 1px solid #E5E7EB;
  text-align: left;
}

/* Body */
table.data tbody td {
  padding: 10px 12px;
  border-bottom: 1px solid #F3F4F6;
  color: #111827;
}

/* Row hover */
table.data tbody tr:hover {
  background: #F9FAFB;
}

/* Clickable row */
table.data tbody tr.row-click {
  cursor: pointer;
}
```

### 2.6 Cards

```css
.card {
  background: white;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  /* No shadow by default — add only on hover if needed */
}

/* Card header */
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #F3F4F6;
}

.card-head h3 {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}

/* Card body */
.card-body {
  padding: 16px;
}
```

### 2.7 KPI Cards (Compact)

```css
.kpi {
  padding: 12px 14px;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  background: white;
}

.kpi-label {
  font-size: 11px;
  font-weight: 600;
  color: #6B7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: #111827;
  margin-top: 4px;
  font-variant-numeric: tabular-nums;
}

.kpi-sub {
  font-size: 11px;
  color: #9CA3AF;
  margin-top: 2px;
}
```

### 2.8 Filter Row

```css
.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-row .input,
.filter-row .select {
  height: 32px;
  padding: 0 10px;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  font-size: 13px;
  background: white;
}

.filter-row .select {
  min-width: 120px;
}
```

### 2.9 Agent Workflow Display

```
Agent 1 ──→ Agent 2 ──→ Agent 3 ──→ Agent 4 ──→ Human Review
Detection    Verification  Evidence     Alert      Pending
✓ Complete   ✓ Complete    ✓ Complete   ✓ Complete
```

**Rules:**
- Horizontal layout with connecting lines
- Each step: name + status
- Status: small green check + "Complete" or spinner + "Running"
- Connecting line: 1px gray, dashed when pending
- No animations, no glow effects
- Maximum 2 lines per step

### 2.10 Investigation Case Detail

```
┌─────────────────────────────────────────────────────────────┐
│ CASE-001                              HIGH    Under Review  │
│ Rapid Geographic Transaction                               │
├─────────────────────────────────────────────────────────────┤
│ SUMMARY                                                     │
│ The same beneficiary completed transactions at two          │
│ geographically distant FPS centers within 11 minutes.       │
├─────────────────────────────────────────────────────────────┤
│ EVIDENCE                                                    │
│ ┌─────────────┬─────────────┬─────────────┬──────────────┐ │
│ │ Transaction │ Timestamp   │ FPS         │ District     │ │
│ ├─────────────┼─────────────┼─────────────┼──────────────┤ │
│ │ TX-001      │ 10:00 AM    │ FPS-DL-0174 │ North Delhi  │ │
│ │ TX-002      │ 10:11 AM    │ FPS-MH-0482 │ Mumbai       │ │
│ └─────────────┴─────────────┴─────────────┴──────────────┘ │
│ Time gap: 11 minutes | Distance: 1,148 km                  │
│ Threshold: > 60 min interval, > 100 km distance            │
├─────────────────────────────────────────────────────────────┤
│ AGENT TRACE                                                 │
│ Agent 1 — Detection ✓ Complete (expandable)                 │
│ Agent 2 — Verification ✓ Complete (expandable)              │
│ Agent 3 — Evidence ✓ Complete (expandable)                  │
│ Agent 4 — Alert ✓ Complete (expandable)                     │
├─────────────────────────────────────────────────────────────┤
│ [Escalate]  [Dismiss]  [Request More Evidence]              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Page Layouts

### 3.1 Command Center

**Current:** Large subtitle, data status section, filters, executive summary, risk tables, charts, insights, alerts, actions — all visible at once.

**Redesigned:**

```
┌──────────────────────────────────────────────────────────────┐
│ Command Center                                               │
│ Monitor PDS activity, investigate anomalies.                 │
│                                                              │
│ [Generate Report]  [Refresh]                                 │
├──────────────────────────────────────────────────────────────┤
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │
│ │ 59   │ │ 81   │ │ 3    │ │ 8    │ │ 4    │ │ 99.8 │     │
│ │Trans │ │Anomal│ │Cases │ │Alerts│ │Sources│ │%     │     │
│ │      │ │ies   │ │Open  │ │Active│ │      │ │Health│     │
│ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘     │
├──────────────────────────────────────────────────────────────┤
│ Filters: [State ▾] [District ▾] [FPS ▾] [Commodity ▾]      │
├──────────────────────────────────────────────────────────────┤
│ RECENT INVESTIGATIONS                                        │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Case     │ Beneficiary │ FPS      │ Anomaly │ Sev │ Stat│ │
│ │──────────│─────────────│──────────│─────────│─────│─────│ │
│ │ CASE-001 │ BEN-DL-10482│ FPS-DL-… │ Rapid…  │ HIGH│ Open│ │
│ │ CASE-002 │ BEN-UP-58321│ FPS-UP-… │ Rapid…  │ MED │ Rev │ │
│ └──────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────┐ ┌─────────────────────────────┐  │
│ │ ALERTS                  │ │ RECENT ANALYSIS             │  │
│ │ • HIGH Rapid geo… 2m ago│ │ • 81 anomalies detected    │  │
│ │ • MED Failure rate 1h   │ │ • 3 cases under review     │  │
│ │ • LOW Inventory 3h      │ │ • Last run: 2 min ago      │  │
│ └─────────────────────────┘ └─────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 AI Analysis

**Current:** Large title + subtitle + command center link + Run button + dataset selector + analysis configuration with checkboxes + filters + precheck + history.

**Redesigned:**

```
┌──────────────────────────────────────────────────────────────┐
│ AI Analysis                                                  │
│ Run the multi-agent investigation workflow.                  │
│                                                              │
│ Dataset: [Synthetic Demo Dataset ▾]  [Run Analysis]         │
├──────────────────────────────────────────────────────────────┤
│ ANALYSIS TYPES                                               │
│ ┌────────────────────────────────────────────────────────┐   │
│ │ ☑ Distribution Anomaly Detection                       │   │
│ │ ☑ Recommendations & Alerts                             │   │
│ │ ☑ Operational Risk                                     │   │
│ │ ☑ Inventory Risk                                       │   │
│ │ ☑ Demand Forecasting                                   │   │
│ └────────────────────────────────────────────────────────┘   │
│                                                              │
│ FILTERS                                                      │
│ [Commodity ▾] [FPS code ▾] [District ▾] [From] [To]        │
├──────────────────────────────────────────────────────────────┤
│ WORKFLOW                                                     │
│ Agent 1 ──→ Agent 2 ──→ Agent 3 ──→ Agent 4                 │
│ Detection    Verify      Evidence     Alert                  │
│ ✓ Done       ✓ Done      ✓ Done       ✓ Done                │
├──────────────────────────────────────────────────────────────┤
│ RESULTS (21 insights)                                        │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Sev │ Type         │ Finding              │ Status │ Act │ │
│ │─────│──────────────│──────────────────────│────────│─────│ │
│ │ HIGH│ Distribution │ Rapid geo… detected  │ Verified│ View│ │
│ │ MED │ Operational  │ High failure rate    │ Open   │ View│ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 Alerts

```
┌──────────────────────────────────────────────────────────────┐
│ Alerts                                                 (8)  │
│ Active alerts requiring review.                              │
│                                                              │
│ [All ▾] [Critical ▾] [Type ▾] [Status ▾]                  │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Priority │ Alert              │ Case     │ Created │ Stat│ │
│ │──────────│────────────────────│──────────│─────────│─────│ │
│ │ ● CRITICAL│ Source failure    │ —        │ 2h ago  │Open │ │
│ │ ● HIGH   │ Rapid geo trans…   │ CASE-001 │ 5m ago  │Open │ │
│ │ ● MEDIUM │ High failure rate  │ CASE-002 │ 1h ago  │Rev │ │
│ │ ● LOW    │ Low inventory      │ —        │ 3h ago  │Ack │ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 3.4 Beneficiaries

```
┌──────────────────────────────────────────────────────────────┐
│ Beneficiaries                                                │
│ Synthetic beneficiary records for demo.                      │
│                                                              │
│ Search...  [District ▾] [Status ▾] [Category ▾]            │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ ID          │ District  │ FPS     │ Txns │ Last    │Risk│ │
│ │─────────────│───────────│─────────│──────│─────────│────│ │
│ │ BEN-DL-10482│ North Del │ FPS-DL… │  12  │ Jul 8   │ LOW│ │
│ │ BEN-UP-58321│ Lucknow   │ FPS-UP… │   8  │ Jul 7   │ MED│ │
│ └──────────────────────────────────────────────────────────┘ │
│ < 1 2 3 ... 10 >                                             │
└──────────────────────────────────────────────────────────────┘
```

### 3.5 Inventory

```
┌──────────────────────────────────────────────────────────────┐
│ Inventory                                                    │
│ Current stock levels and risk assessment.                    │
│                                                              │
│ [FPS ▾] [Commodity ▾] [Risk ▾]                             │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ FPS      │ Commodity │ Stock │ Monthly │ Days │ Risk     │ │
│ │──────────│───────────│───────│─────────│──────│──────────│ │
│ │ FPS-DL-1 │ Rice      │ 500kg │ 200kg   │  75  │ LOW      │ │
│ │ FPS-MH-3 │ Wheat     │  50kg │ 180kg   │   8  │ CRITICAL │ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 3.6 Reports

```
┌──────────────────────────────────────────────────────────────┐
│ Reports                                                      │
│ Generate investigation and analysis reports.                 │
│                                                              │
│ [Investigation Report] [Anomaly Summary] [District Risk]     │
├──────────────────────────────────────────────────────────────┤
│ RECENT REPORTS                                               │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ Title              │ Type        │ Generated │ Actions   │ │
│ │────────────────────│─────────────│───────────│───────────│ │
│ │ Investigation #1   │ Investigation│ 2m ago   │ [View] [DL]│ │
│ │ Anomaly Summary    │ Summary     │ 1h ago    │ [View] [DL]│ │
│ └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Navigation Hierarchy

```
OVERVIEW
  ├── Command Center    (default landing)
  └── Overview          (analytics dashboard)

DATA
  ├── Beneficiaries
  ├── Ration Distribution
  ├── Inventory
  ├── Import Data
  └── Data Sources

INTELLIGENCE
  ├── AI Analysis       (primary workflow page)
  ├── Analytics
  ├── AI Insights
  ├── Alerts
  └── Decision Support

REPORTING
  └── Reports

SYSTEM
  └── Settings
```

---

## 5. Responsive Behavior

### Desktop (1280px+)
- Sidebar: 220px
- Content: remaining width
- KPI grid: 4-6 columns
- Tables: full width

### Laptop (1024px–1279px)
- Sidebar: 220px
- KPI grid: 3 columns
- Tables: full width

### Tablet (768px–1023px)
- Sidebar: hidden (hamburger toggle)
- Content: full width
- KPI grid: 2 columns
- Bottom nav: visible

### Mobile (< 768px)
- Sidebar: overlay (slide-in)
- Content: full width
- KPI grid: 1 column
- Bottom nav: visible
- Tables: horizontal scroll

---

## 6. Implementation Instructions

### Step 1: CSS Variables Update

Update `:root` in `styles.css` with the refined values from Section 1.1.

### Step 2: Sidebar Refinement

1. Reduce width from 252px to 220px
2. Remove collapse button — always full width
3. Reduce brand mark size
4. Tighten nav item padding
5. Simplify active state

### Step 3: Top Header Simplification

1. Reduce height from 60px to 52px
2. Remove backdrop-filter blur
3. Simplify search trigger
4. Reduce profile button to avatar only
5. Use simpler breadcrumb styling

### Step 4: Button Refinement

1. Reduce default height from 38px to 32px
2. Use smaller border-radius (6px)
3. Reduce font size to 13px
4. Simplify hover states

### Step 5: Badge Refinement

1. Use 11px font size
2. Reduce padding to 2px 8px
3. Use softer background colors
4. Remove unnecessary dots

### Step 6: Table Refinement

1. Reduce cell padding
2. Use lighter row borders
3. Simplify header styling
4. Add subtle row hover

### Step 7: Card Refinement

1. Remove default box-shadow
2. Use 8px border-radius
3. Reduce internal padding
4. Simplify card headers

### Step 8: KPI Card Refinement

1. Use 22px font size for values
2. Remove spark charts by default
3. Use compact layout
4. Add subtle border

### Step 9: Page Content Simplification

1. Reduce page titles to 20px
2. Shorten subtitles
3. Remove redundant descriptions
4. Use progressive disclosure

### Step 10: Agent Workflow Display

1. Create clean horizontal step display
2. Use simple status indicators
3. No animations or effects
4. Clear connecting lines

---

## 7. What NOT to Change

- ✅ All backend logic
- ✅ All API contracts
- ✅ All agent architecture
- ✅ All business logic
- ✅ All data flows
- ✅ All functionality
- ✅ All existing features
- ✅ Color palette (just refine)
- ✅ Typography family (just refine sizes)

---

## 8. Testing Checklist

After implementation, verify:

- [ ] Sidebar navigation works
- [ ] All pages render correctly
- [ ] Tables display properly
- [ ] Badges show correct colors
- [ ] Buttons function correctly
- [ ] Filters work
- [ ] Responsive layout works
- [ ] Mobile bottom nav works
- [ ] Search works
- [ ] Dropdowns work
- [ ] Modals/drawers work
- [ ] Charts render
- [ ] Loading states work
- [ ] Error states work
- [ ] Empty states work
- [ ] All API calls work
- [ ] Agent workflow displays
- [ ] Investigation cases open
- [ ] Evidence tables show
- [ ] Reports generate
