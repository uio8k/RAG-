# DESIGN.md: Heidi Health Landing Page → StockX Pro

## Source
- URL: https://www.heidihealth.com/en-gb
- Capture date: 2026-05-31
- Evidence: Firecrawl branding scrape + full-page screenshot + content markdown

## Reference Screenshot
![Full-page screenshot of Heidi Health](./.firecrawl/heidi-health-screenshot.png)

Use this screenshot as the visual source of truth for layout, hierarchy, density, and feel.

## Design Summary

Heidi Health employs a **warm, clean, clinical-modern** aesthetic. The design language conveys trust, clarity, and professionalism — ideal for a financial dashboard like StockX Pro. The palette is anchored by a warm off-white background, a distinctive golden-yellow primary accent, and deep brown-black typography. Typography pairs the authoritative serif Georgia for headlines with the clean sans-serif Inter for body text. The overall feel is spacious, calm, and premium without feeling cold.

## Design Tokens

### Colors
| Role | Hex | Usage |
|------|-----|-------|
| Primary / Accent | `#FBF582` | Primary buttons, key indicators, positive change |
| Secondary | `#755760` | Section headers, subtle accents, nav active states |
| Background | `#FCFAF8` | Page background (warm off-white) |
| Card Background | `#FFFFFF` | Card surfaces, content containers |
| Text Primary | `#28030F` | Body text, headings (deep brown-black) |
| Text Secondary | `#6B5E62` | Secondary text, muted labels (derived from secondary) |
| Border Light | `#EDE8E4` | Card borders, dividers (derived from background) |
| Positive/Green | `#2FA84F` | Price up, profit indicators |
| Negative/Red | `#D93A3A` | Price down, loss indicators |

### Typography
- **Headings**: Georgia, serif — authoritative, professional
  - h1: ~48px, h2: ~40px, h3: ~28px, h4: ~22px
- **Body**: Inter, system-ui, sans-serif — clean, readable
  - Body: 16px, small: 14px, caption: 12px
- **Font Stack**: `'Georgia', 'Times New Roman', serif` for headings; `'Inter', system-ui, -apple-system, sans-serif` for body
- **Fallback**: Use system serif/sans-serif stacks when web fonts unavailable

### Spacing And Layout
- **Base unit**: 4px
- **Container max-width**: 1200px
- **Section padding**: 60px vertical, 24px horizontal
- **Card padding**: 24px
- **Border radius**: 12px (primary buttons, cards), 6px (secondary elements)
- **Shadows**: Subtle warm shadows — `0 1px 3px rgba(120,90,60,0.06)`

## Components

### Buttons
- **Primary**: `background: #FBF582; color: #28030F; border-radius: 12px; padding: 12px 28px; font-weight: 600;` — warm yellow, dark text
- **Secondary**: `background: #FFFFFF; color: #28030F; border: 1px solid #EDE8E4; border-radius: 6px;`
- **Hover**: Primary darkens slightly to `#F5E84D`; secondary gets a subtle background tint

### Cards
- White background, subtle border (`#EDE8E4`), 12px border radius
- Warm shadow: `0 2px 8px rgba(120,90,60,0.06)`
- Hover: slight lift (`translateY(-2px)`) with deeper shadow

### Navigation
- Clean top navbar, light background, minimal border-bottom
- Active link: Secondary color (`#755760`) underline or background tint
- Logo area: left-aligned, bold Georgia typeface

### Stats / Dashboard Cards
- Large Georgia numbers for key metrics
- Inter labels below
- Green accent for positive, red for negative values

## Page Patterns
- **Hero/Dashboard**: Top banner with key metrics → grid of cards → detailed sections
- **Detail pages**: Breadcrumb → header with stock info → chart → data tables
- **Lists**: Clean table with alternating subtle row backgrounds

## Agent Build Instructions
1. Use Bootstrap 5 for grid system and responsive utilities
2. Use Chart.js for financial charts (line charts for NAV, bar charts for comparisons)
3. Import Inter and Georgia from Google Fonts
4. Apply the color tokens above as CSS custom properties on `:root`
5. Keep component markup semantic and accessible
6. Maintain the warm, spacious feel — generous padding, clear hierarchy, gentle shadows

## Rerun Inputs
workflow: firecrawl-website-design-clone
source_url: https://www.heidihealth.com/en-gb
target_stack: Bootstrap 5 + Chart.js + Django Templates
output: DESIGN.md
