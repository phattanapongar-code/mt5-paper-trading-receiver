# Design

## Theme

Dark cyberpunk — trading control room aesthetic.

- **Background**: `#06060e` (surface-900)
- **Surface**: `#0a0a18` (surface-800), `#0f0f24` (surface-700), `#14142e` (surface-600)
- **Border**: `#1a1a3e` (surface-500)
- **Text**: `#e2e8f0` (primary), `#94a3b8` (secondary), `#64748b` (muted)

## Color Palette (OKLCH)

| Token | Color | Usage |
|-------|-------|-------|
| cyber-cyan | `#00f0ff` | Primary accent, active state, info |
| cyber-green | `#00ff88` | Buy, profit, online, bullish |
| cyber-red | `#ff3355` | Sell, loss, offline, bearish |
| cyber-yellow | `#ffcc00` | Warning, pending, RR indicator |
| cyber-magenta | `#ff33cc` | Secondary accent, ATR |
| cyber-purple | `#8833ff` | MA300 indicator line |

## Typography

- **UI**: Inter (system-ui fallback) — 400/500/600/700 weights
- **Data/Monospace**: JetBrains Mono (ui-monospace fallback) — 400/500/600 weights
- **Scale**: 12/13/14/15/16/18/20/24px (no fluid typography)
- **Line length**: 65-75ch for prose; data tables can run denser

## Components

### Cards
- Background: `surface-800`, border: `surface-500`, border-radius: 8px
- Padding: 16px, no shadow (border-only)
- Accent variants: left border color for status indication

### Tables
- Header: `text-text-muted` 12px uppercase tracking, border-bottom `surface-500`
- Row: hover `surface-700/50`, border-bottom `surface-600`
- Cell padding: 12px, monospace for numeric data

### Buttons
- Primary: `cyan` accent with `bg-cyber-cyan/20 border-cyber-cyan/50`
- Toggle: `green` (enabled) / `red` (disabled) with matching bg/border
- Ghost: `surface-700` bg, `surface-500` border, subtle hover

### Sidebar Navigation
- Width: 224px (collapsed: 64px)
- Active item: `bg-cyber-cyan/10`, `border-l-2 border-cyber-cyan`
- Inactive item: `text-text-secondary`, `hover:bg-surface-600`

### Inputs
- Background: `surface-800`, border: `surface-400`
- Focus: `border-cyber-cyan ring-1 ring-cyber-cyan/30`
- Border-radius: 8px

## Layout

- Full-height flex: sidebar (fixed) + main content (scrollable)
- Sidebar: top logo, nav links, logout at bottom
- Main: padding 24px, max-width 1280px
- Grid: 1/2/3/4 column responsive via breakpoints
- No cards nested inside cards

## Motion

- 150-250ms transitions on state changes (hover, toggle, navigation)
- No decorative animation
- `prefers-reduced-motion`: disable all transitions
- `transition-colors` for interactive elements only

## Interactive States

Every interactive element has: default, hover, focus-visible, active, disabled.

- Focus visible: `ring-2 ring-cyber-cyan/50`
- Disabled: `opacity-40 cursor-not-allowed`
- No custom scrollbars beyond thin WebKit styling
