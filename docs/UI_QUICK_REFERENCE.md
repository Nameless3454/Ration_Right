# RationRight UI Redesign — Quick Reference Card

## Color Palette

```css
--forest: #14532D;      /* Primary green */
--emerald: #059669;     /* Accent green */
--bg: #F9FAFB;          /* Page background */
--card: #FFFFFF;        /* Content surfaces */
--text: #111827;        /* Primary text */
--text-2: #6B7280;      /* Secondary text */
--text-3: #9CA3AF;      /* Tertiary text */
--border: #E5E7EB;      /* Borders */
--success: #059669;     /* Success */
--warning: #D97706;     /* Warning */
--error: #DC2626;       /* Error */
--info: #2563EB;        /* Info */
```

## Spacing Scale

```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
```

## Typography

| Element | Size | Weight |
|---------|------|--------|
| Page title | 20px | 700 |
| Section title | 11px | 700 |
| Card header | 13px | 600 |
| Body text | 13px | 400 |
| Caption | 12px | 500 |
| Badge | 11px | 600 |
| Nav label | 13px | 500 |

## Component Sizes

| Component | Size |
|-----------|------|
| Sidebar width | 220px |
| Top header height | 52px |
| Button height | 32px |
| Input height | 32px |
| Badge padding | 2px 8px |
| Card radius | 8px |
| Button radius | 6px |

## Badge Colors

```css
.badge.critical { color: #991B1B; background: #FEF2F2; }
.badge.high     { color: #991B1B; background: #FEF2F2; }
.badge.medium   { color: #92400E; background: #FFFBEB; }
.badge.low      { color: #065F46; background: #ECFDF5; }
.badge.info     { color: #1E40AF; background: #EFF6FF; }
.badge.success  { color: #065F46; background: #ECFDF5; }
.badge.neutral  { color: #374151; background: #F3F4F6; }
```

## Key CSS Rules

### Sidebar
```css
.sidebar { width: 220px; }
.sidebar-collapse { display: none; }
.nav a { padding: 7px 12px; font-size: 13px; }
.nav a.is-active { background: var(--pale-green); }
```

### Top Header
```css
.topbar { height: 52px; background: var(--card); }
.search-trigger { height: 32px; min-width: 160px; }
.profile-btn-text { display: none; }
```

### Buttons
```css
.btn { height: 32px; border-radius: 6px; font-size: 13px; }
.btn-primary { background: var(--forest); }
```

### Tables
```css
table.data thead th { font-size: 11px; padding: 8px 12px; }
table.data tbody td { padding: 10px 12px; }
```

### Cards
```css
.card { border-radius: 8px; /* No shadow */ }
.card-head { padding: 12px 16px; }
.card-body { padding: 16px; }
```

## Implementation Steps

1. Update `:root` CSS variables
2. Refine sidebar (width, padding, active state)
3. Simplify top header (height, search, profile)
4. Compact buttons (height, radius, padding)
5. Refine badges (size, colors, padding)
6. Clean tables (padding, borders, hover)
7. Simplify cards (radius, shadow, padding)
8. Update forms (height, radius)
9. Simplify page content (titles, subtitles)
10. Remove visual effects (gradients, animations)
11. Update responsive rules
12. Remove collapse functionality

## Testing Checklist

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
- [ ] All API calls work
- [ ] Agent workflow displays
- [ ] Investigation cases open
- [ ] Evidence tables show
- [ ] Reports generate

## Quick Commands

```bash
# Start server
cd /Users/sahoo/Documents/RationRight
python3 server.py

# Run tests
python3 -m pytest tests/ -v

# Check CSS
grep -n "var(--" static/styles.css | head -20

# Check HTML
grep -n "sidebar-collapse" static/index.html
```

## Key Files

- `static/styles.css` — Main CSS
- `static/index.html` — HTML structure
- `static/app.js` — JavaScript logic
- `docs/UI_REDESIGN_SPEC.md` — Full spec
- `docs/UI_REDESIGN_IMPLEMENTATION.md` — Step-by-step guide
