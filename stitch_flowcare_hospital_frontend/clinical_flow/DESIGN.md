---
name: Clinical Flow
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#3f4850'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#707881'
  outline-variant: '#bfc7d2'
  surface-tint: '#006398'
  primary: '#006194'
  on-primary: '#ffffff'
  primary-container: '#007bb9'
  on-primary-container: '#fdfcff'
  inverse-primary: '#93ccff'
  secondary: '#0051d5'
  on-secondary: '#ffffff'
  secondary-container: '#316bf3'
  on-secondary-container: '#fefcff'
  tertiary: '#545c72'
  on-tertiary: '#ffffff'
  tertiary-container: '#6c748b'
  on-tertiary-container: '#fefcff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#cce5ff'
  primary-fixed-dim: '#93ccff'
  on-primary-fixed: '#001d31'
  on-primary-fixed-variant: '#004b73'
  secondary-fixed: '#dbe1ff'
  secondary-fixed-dim: '#b4c5ff'
  on-secondary-fixed: '#00174b'
  on-secondary-fixed-variant: '#003ea8'
  tertiary-fixed: '#dae2fd'
  tertiary-fixed-dim: '#bec6e0'
  on-tertiary-fixed: '#131b2e'
  on-tertiary-fixed-variant: '#3f465c'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.025em
  display-md:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 22px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
  tabular-stat:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 28px
    letterSpacing: -0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-wall: 1.5rem
  margin: 1.5rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system delivers an operational interface tailored for clinical administrators, charge nurses, unit directors, and hospital incident command teams. The environment demands calm authority, extreme reliability, and cognitive ease under high-stress conditions. 

The aesthetic is Modern Clinical Minimalist: utilitarian, disciplined, and strictly purposeful. It rejects decorative trends, skeuomorphic flourishes, and saturated novelty in favor of clear information architecture, high legibility, and unmistakable visual hierarchy. Every visual artifact corresponds directly to real-world operational truth—capacity levels, bed turnaround, patient transit stages, and staff assignments. Visual calm reduces cognitive fatigue across 12-hour shifts, while robust contrast ensures visibility both on clinician laptops and distant wall-mounted unit telemetry displays.

## Colors

The palette establishes an immaculate, high-clarity environment anchored by structured light slates, deep navy typography, and functional semantic indicators.

### Base Canvases & Boundaries
- **App Canvas:** `#F8FAFC` (Slate 50) provides an anti-glare foundation for long operational shifts.
- **Card & Surface Container:** `#FFFFFF` (Pure White) defines actionable cards, data tables, and modal layers.
- **Subtle Surface Tint:** `#F1F5F9` (Slate 100) separates secondary controls, table headers, and inactive states.
- **Structural Borders:** `#E2E8F0` (Slate 200) structures grid lines, cell dividers, and container bounds without high visual clutter.
- **Subtle Dividers:** `#F1F5F9` provides intra-component separation.

### Typography & Readability
- **Primary Body & Display:** `#0F172A` (Slate 900) ensures near-black optical contrast exceeding WCAG AAA standards.
- **Secondary / Supporting Metadata:** `#475569` (Slate 600) for timestamps, census identifiers, and table headers.
- **Muted / Placeholder:** `#94A3B8` (Slate 400) for disabled fields, empty states, and inactive icons.

### Primary Accents & Active States
- **Primary Clinical Blue:** `#0284C7` (Sky 600) for primary command actions, focused inputs, and primary navigation active state.
- **Operational Blue / In-Progress:** `#2563EB` (Blue 600) paired with `#DBEAFE` (Blue 100) for occupied beds, admitted transit states, and active telemetry.

### Semantic Status Architecture
Status colors are reserved exclusively for operational triage and must never be co-opted for purely decorative elements:
- **Available / Normal Flow:** Text and icons `#16A34A` (Green 600) on `#DCFCE7` (Green 100). Indicates bed readiness, normal turnaround times, and stable capacity (<85%).
- **Warning / Cleaning / High Utilization:** Text and icons `#D97706` (Amber 600) on `#FEF3C7` (Amber 100). Indicates beds pending housekeeping, units operating at 85%–95% threshold, or delayed discharges.
- **Occupied / Active Operation:** Text and icons `#2563EB` (Blue 600) on `#DBEAFE` (Blue 100). Indicates beds with active patients and normal care pathways.
- **Critical Alert / Escalation:** Text and icons `#DC2626` (Red 600) on `#FEE2E2` (Red 100). Reserved strictly for saturation alerts (>95% capacity), diversion protocols, rapid response events, and unassigned telemetry alerts.

## Typography

The type system is powered by Inter across all tiers, chosen for its neutral tone, open apertures, and tall x-height. 

### Operational Rules
- **Tabular Numerals (`font-feature-settings: "tnum"`):** Mandatory across all metric displays, telemetry counts, bed capacity tallies, and timestamps to eliminate jitter and maintain horizontal alignment across rapid refresh cycles.
- **Case Formatting:** Use uppercase only for `label-sm` when designating short status badges (e.g., `OCCUPIED`, `STAT`, `DIRTY`, `READY`) with `+0.04em` letter-spacing. All headlines and metric explanations remain in standard sentence case.
- **Wall Display Readability:** On large-format telemetry boards (viewed at 3–5 meters), the base metric utilizes `display-lg` alongside `headline-sm` labels to ensure immediate glanceability without ocular strain.

## Layout & Spacing

The layout is built around high-density data requirements that balance compact efficiency with breathing room to eliminate reading errors.

### Grid Infrastructure
- **Desktop (1280px to 1920px):** 12-column fluid grid, `1.5rem` margins, `1rem` column gutters. Suitable for split-screen EHR side-by-sides, bed boards, and patient transit logs.
- **Large-Format Telemetry Displays (1920px+):** Standardized 16-column grid with `1.5rem` gutters and `2rem` margins, enabling 4-, 8-, or 16-block department overviews (ED, ICU, Med-Surg, PACU).
- **Tablet / Mobile (<= 1024px):** 4 to 8 columns with `1rem` margins and `0.75rem` gutters, prioritizing vertical operational feeds and single-column unit cards.

### Density Rhythms
- **Data Tables:** Dense layout with vertical cell padding constrained to `0.5rem` (`space-sm`) and horizontal padding at `0.75rem` (`space-md`), keeping high volumes of patient flow within initial viewport bounds.
- **Tile Grids (Bed Management):** Unit bed matrices use `space-sm` internal padding with `space-md` gaps to represent bed wards clearly while maximizing on-screen inventory.

## Elevation & Depth

To preserve clinical focus and reduce visual weight, this design system rejects heavy, diffused drop shadows and glassmorphism. Depth is achieved via **low-contrast outlines** paired with disciplined **tonal layers**.

### Surface Hierarchy
1. **Base Layer (`#F8FAFC`):** Global canvas behind dashboards and telemetry panels.
2. **Container Tier (`#FFFFFF`):** Base surface for all data grids, unit cards, patient lists, and metric counters. Containers are bounded by a clean `1px solid #E2E8F0` border.
3. **Elevated Overlays & Flyouts:** Drawers, command palettes, and modal dialogs retain a `#FFFFFF` background with an ultra-fine border (`#CBD5E1`) and a direct, highly controlled structural shadow: `0 4px 12px -2px rgba(15, 23, 42, 0.08)`.
4. **Focused / Critical Priority Items:** Emphasized via a high-contrast `2px solid #0284C7` outline or status-relevant semantic outline (e.g., `#DC2626` for capacity surge alerts).

## Shapes

The design system maintains a calibrated **Soft** roundedness scale (Base radius: `0.25rem` / `4px`). This maintains crisp clinical edges that integrate cleanly into grid-dense tabular and analytical layouts without appearing severe.

- **Base Radius (`0.25rem` / `4px`):** Applied to buttons, data table rows, input fields, dropdown menus, and bed status chips.
- **Large Radius (`rounded-lg`, `0.5rem` / `8px`):** Applied to major dashboard cards, metric tiles, patient overview panels, and modal containers.
- **Pill Radius (`rounded-full`):** Reserved exclusively for high-priority numeric notification badges and semantic dot indicators to contrast with rectangular operational cards.

## Components

### Action Controls (Buttons)
- **Primary Command:** Solid `#0284C7` background, `#FFFFFF` text, `4px` corner radius, `label-lg` font weight. On hover: `#0369A1`. Used for main operational actions (e.g., "Admit Patient", "Assign Bed").
- **Secondary Command:** `#FFFFFF` background, `1px solid #E2E8F0`, `#0F172A` text. On hover: `#F1F5F9` background and `#CBD5E1` border.
- **Destructive / Urgent Action:** `#DC2626` background, `#FFFFFF` text. Reserved strictly for unit-level locks, code events, or diversion confirmations.
- **Dimensions:** Compact (`32px` height) for dense clinical desktop workflows; standard (`40px` height) for touch-enabled wall terminals.

### Status Chips & Badges
- Chips are non-interactive semantic indicators communicating state in 1–2 words.
- Structure: `20px` height, `4px` radius, `label-sm` uppercase text with `0.5rem` horizontal padding.
- Combinations:
  - **Available:** `#DCFCE7` background with `#15803D` text.
  - **Cleaning / Delayed:** `#FEF3C7` background with `#B45309` text.
  - **Occupied / Active:** `#DBEAFE` background with `#1D4ED8` text.
  - **Critical Surge:** `#FEE2E2` background with `#B91C1C` text.

### Data Tables (Patient Flow & Unit Census)
- **Header:** `#F8FAFC` background, `1px solid #E2E8F0` top and bottom borders, `#475569` uppercase `label-md` text.
- **Rows:** `#FFFFFF` background, single `1px solid #F1F5F9` bottom divider. Alternate row striping is omitted in favor of a subtle `#F8FAFC` hover fill on row focus.
- **Cells:** Align numbers right, text left, and operational status badges centered.

### Bed Matrix & Unit Capacity Cards
- Modular grid cards representing bed units (e.g., `ICU-04`, `ED-12`).
- Card layout: Top bar with bed label (`headline-sm`) and status chip (`label-sm`). Middle zone displaying patient tracking hash, acuity level, and elapsed turnaround time using tabular numerals (`tabular-stat`). Bottom zone showing housekeeping or physician assignment metadata.
- Border indicator: When a unit exceeds standard thresholds or reports an alert, the entire card boundary changes from `#E2E8F0` to a `2px solid` semantic boundary (`#D97706` for overdue cleaning, `#DC2626` for telemetry alert).

### Form Inputs & Filters
- Base input height: `36px` on desktop. Background `#FFFFFF` with `1px solid #CBD5E1` border.
- Focus state: `1px solid #0284C7` with a non-diffused `2px` focus ring (`rgba(2, 132, 199, 0.15)`).
- Error state: `1px solid #DC2626` with explicit supporting text in `label-sm`.

### Metric HUD Panels
- Standalone tiles summarizing key operational indicators: Net Admissions, Pending Discharges, Housekeeping Queue, System Capacity %.
- Composed of `display-md` tabular values in `#0F172A`, labeled by `label-md` uppercase text in `#475569`, accompanied by a semantic micro-pill indicating trend delta over the last 60 minutes.