# Frontend UI/UX Blueprint — Web Modernizer Portal

## Purpose

This document is a UI/UX blueprint for replicating the look and feel of the Angular frontend (`portal/`) in a separate project. It covers foundational setup, a design-token system to extract (the source app has none — colors are hardcoded per file), and a section-by-section breakdown of every distinct visual area: **Header, Hero, Welcome page, History page, Progress page**.

All details below are drawn directly from the source files in `portal/src/app`.

---

## 1. Foundational Setup (apply once, first)

- **Framework**: Angular 20.3, 100% standalone components (no NgModules), signals for state (`signal`/`computed`/`effect`), new `@if`/`@for` control-flow syntax, esbuild builder (`@angular/build:application`).
- **No UI kit, no CSS framework**: no Material/PrimeNG/Bootstrap/Tailwind. All styling is hand-rolled SCSS per component. Reproduce this hand-rolled aesthetic — don't introduce a component library unless the replica intentionally uses a different stack.
- **Font**: Google Fonts "Inter", weights 400/500/600/700, loaded via `<link>` preconnect in `index.html`. Fallback stack: `'Inter', system-ui, -apple-system, sans-serif`.
- **Base reset & page background** (`src/styles.scss`):
  ```scss
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    height: 100%;
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    font-size: 16px;
    background: #0f0f23;
    color: #f0f0f0;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  ```
- **Design tokens to formalize** (the source app hardcodes these repeatedly per-component — in the replica, define them once as SCSS variables or CSS custom properties):

  | Token | Value | Usage |
  |---|---|---|
  | `--bg-page` | `#0f0f23` | page background |
  | `--bg-elevated` | `#1a1a2e` | cards, dropdowns |
  | `--bg-elevated-2` | `#12121f` / `#1e1e2e` | nested surfaces |
  | `--border-subtle` | `rgba(255,255,255,0.06)` – `0.08` | dividers, card borders |
  | `--border-card` | `#2a2a45` | card borders (history/progress cards) |
  | `--text-primary` | `#f0f0f0` | headings, body |
  | `--text-secondary` | `#888` | subtext |
  | `--text-muted` | `#555` / `#666` | hints, placeholders |
  | `--accent-primary` | `#6c63ff` (purple) | primary brand color |
  | `--accent-secondary` | `#4ecdc4` (teal) | gradient partner |
  | `--accent-tertiary` | `#a855f7` (magenta) | alt gradient partner (buttons, badges) |
  | `--gradient-brand` | `linear-gradient(135deg, #6c63ff, #4ecdc4)` | logo text, avatar fallback |
  | `--gradient-button` | `linear-gradient(135deg, #6c63ff, #5a54e8)` | primary CTAs |
  | `--gradient-accent-2` | `linear-gradient(135deg, #6c63ff, #a855f7)` | secondary CTAs, progress fills |
  | `--success` | `#34d399` / `#4ade80` | valid states, completed badges |
  | `--error` | `#ef4444` / `#fca5a5` / `#f87171` | errors, low-credit warnings |
  | border-radius scale | `6px`–`24px` (small controls → hero cards) | — |
  | max content width | `1200px` (navbar), `1100px` (dashboard), `900px` (progress), `860px` (history) | per-page container |

- **Component file convention**: `<name>.component.ts` + `.html` + `.scss` for larger pages; inline `template`/`styles` in `.ts` for small components (root shell, layout wrapper). Selector prefix `app-`.
- **Reusable UI to extract as real components** (the source app duplicates these as copy-pasted CSS classes per page — worth fixing in the replica): `Button` (primary/outline/CTA/download variants), `Spinner` (sm/lg), `ProgressBar`, `Badge`/`TierBadge`/`StatusBadge`, `Card`.

---

## 2. Section: Header (Navbar)

Source: `shared/navbar/navbar.component.html` + `.scss`

- Sticky top bar (`position: sticky; top: 0; z-index: 100`), translucent dark background `rgba(15,15,35,0.85)` with `backdrop-filter: blur(12px)`, bottom border `1px solid rgba(255,255,255,0.06)`.
- Container: max-width `1200px`, centered, `height: 64px`, flex row, `gap: 2rem`.
- **Left**: brand logo — lightning emoji icon + "Web" (plain) + "Modernizer" (gradient-text span using `--gradient-brand`, `background-clip: text`).
- **Center**: nav links (Home / History / Buy Credits) — pill-style, muted gray `#888` default, active state gets `rgba(108,99,255,0.15)` background + light text via `routerLinkActive`.
- **Right side**:
  - Credit balance pill/badge (icon + count + "credit(s)" label), purple tint by default, switches to red tint when balance `<= 1` (`.low` class).
  - Avatar (image or gradient-fallback circle with initial letter) that opens a dropdown menu on click: user name/email header, divider, "My Generations", "Buy Credits", divider, "Sign Out" (danger/red styled).
- Dropdown: absolute-positioned card below avatar, dark surface `#1a1a2e`, rounded `10px`, drop shadow, `fadeDown` entrance animation.
- Replicate structurally even without real auth — swap avatar/credit-badge logic for whatever the new project's identity model is; keep the visual pattern (sticky blurred bar, gradient brand mark, pill nav links, right-aligned status+avatar cluster).

---

## 3. Section: Hero (Dashboard landing)

Source: `features/dashboard/dashboard.component.html` + `.scss` (top `<section class="hero">` block only — the page also has "How It Works", "Features", and bottom CTA sections below the hero, listed here as they share the hero's visual language)

- Centered text hero, `padding: 5rem 0 4rem`, radial purple glow (`hero-bg-glow`, `700x500px`, `rgba(108,99,255,0.18)` ellipse) positioned behind content via absolute positioning + `pointer-events: none`.
- Small pill "badge" above headline (✨ emoji + label), purple-tinted background/border.
- Large headline (`clamp(2rem, 5vw, 3.5rem)`, weight 800, tight letter-spacing) with a gradient-text span (`--gradient-brand`, purple→teal) on the second line for emphasis.
- Subheadline paragraph, muted gray, max-width `580px`, centered.
- Optional inline warning banner (red-tinted) for a blocked/error state.
- **Primary input row** ("url-box"): pill-shaped input container (`border-radius: 14px`, subtle border, focus-glow to purple on `:focus-within`, error/valid border-color states), leading icon, text input, trailing primary gradient button with icon + label, inline spinner swap while loading.
- Inline validation message row below input (icon + red text) and a muted hint row (supports text + a highlighted "credits" pill and dynamic balance count).
- Trust-signal row: 3 short muted text items with emoji icons, centered, wrapping flex row.
- Below the hero: a 3-step "How It Works" card row (numbered cards with icon/title/description, connected by arrow glyphs, alternating to vertical stack on mobile `≤768px`), a responsive feature-card grid (`auto-fit, minmax(300px,1fr)`), and a closing glowing CTA card (`border-radius: 24px`, radial glow overlay, centered heading + gradient button).
- This whole page uses the shared `.container` (max-width `1100px`), `.section` (`padding: 5rem 0`), `.section-label` (small purple uppercase eyebrow), `.section-title` (centered, `clamp`-sized) pattern — reuse those as generic page-section primitives across the new app, not just on the hero.

---

## 4. Section: Welcome page (Login / Auth screen)

Source: `features/auth/login/login.component.html` + `.scss`

- This is the first screen an unauthenticated/new visitor sees — the "welcome" entry point.
- Centered card layout (`.auth-page` full-viewport centering wrapper → `.auth-card`), dark elevated surface, rounded corners.
- Header block inside the card: brand title ("Web Modernizer") + tagline ("Redesign your website with AI").
- **Tab switcher**: two-button segmented control ("Sign In" / "Create Account"), active tab highlighted.
- Global error alert banner (red-tinted) shown above the active form when present.
- **Sign In form**: email-or-username field, password field, per-field inline validation errors, primary submit button with inline spinner + "Signing in…" label while pending.
- **Create Account form**: email, username, optional display name, password, confirm-password (cross-field match validator), a small "You'll receive N free credits to get started" notice line, primary submit button with spinner state.
- **Divider**: "or continue with" centered text with horizontal rule on both sides.
- **Google button**: full-width outline button with the official multi-color Google "G" SVG mark + "Continue with Google" label — visually distinct from the primary gradient buttons elsewhere (white/light button on dark card, per standard Google branding guidelines).
- In the replica, keep this card-centered "welcome" pattern (brand + tagline + tabbed forms + social button) even if the auth backend differs — it's the visual template for any future login/signup screen.

---

## 5. Section: History page

Source: `features/history/history.component.html` + `.scss`

- `.history-page` container, max-width `860px`, centered.
- Page header row: left-aligned title ("My Generations"), right-aligned pill CTA button ("+ New Generation", gradient purple→magenta) — `justify-content: space-between`, wraps on small screens.
- **Loading state**: skeleton list — 3 shimmering placeholder bars (animated gradient sweep, `80px` tall, rounded).
- **Error state**: red-tinted alert banner.
- **Empty state**: centered column — circular icon badge (muted), heading, subtext, primary gradient CTA button linking back to the hero/dashboard.
- **List state**: vertical stack of "gen-card" rows (`gap: 0.75rem`), each a dark elevated card (`#1a1a2e` bg, `#2a2a45` border, hover brightens border) containing:
  - Left: source URL (truncated with ellipsis, tooltip on hover) + relative/formatted date, stacked.
  - Middle: a tier badge (Basic/Pro/Premium — each its own muted color: gray/blue/purple) + a status badge (uppercase pill, purple for in-progress states, green for completed, red for failed) + (if in-progress) an inline mini progress bar with percentage text + (if failed with system error) a green "Credit refunded" note.
  - Right: a "View" / "Watch progress" outline button linking to the relevant progress or preview page.
- Responsive: below `600px`, card content stacks vertically and the action button becomes full-width.
- Badge color system here (tier + status) is a good reusable pattern to formalize as a shared `Badge` component with variant props.

---

## 6. Section: Progress page (generation tracking)

There are two related progress UIs in the source app — replicate both, they share the same visual language:

### 6a. Single-generation progress (`features/generation/generation.component.html` + `.scss`)

- `.gen-page`, max-width `900px`, vertical flex stack.
- Back link ("← Back to Dashboard"), muted, brightens on hover.
- Source URL line, small muted text.
- **In-progress state**: a dark elevated `.progress-card` (rounded `16px`, centered content) containing:
  - A horizontal **stepper**: numbered dots connected by lines; each dot is empty/outlined (pending), filled purple with checkmark (done), or outlined-with-inline-spinner (active); connecting lines fill purple as steps complete; labels beneath each dot.
  - A slim rounded **progress bar** (`6px` tall, purple gradient fill, animated width transition) below the stepper.
  - Status label (current phase, e.g. "Scraping content…") + a muted hint line ("This takes about 30–60 seconds").
- **Failed state**: centered card, red-tinted background/border, large circular "✕" icon, heading, failure reason text, optional green "credit refunded" pill, primary "Try Again" button.
- **Completed state**: a header row (circular checkmark icon + "Your modernized site is ready" heading), then a large **preview iframe** panel (dark placeholder background, centered spinner + "Loading preview…" while the iframe content loads, then fades in), then an actions row (Full Preview / Download ZIP (disabled, "Coming soon") / Redesign (disabled)).
- Shared local button system: pill-shaped (`border-radius: 100px`) `--primary` (solid purple) and `--outline` (transparent, gray border, disabled-dimmed) variants — note this page uses fully-rounded pill buttons vs. the more common `8–14px` rounded-rect buttons used elsewhere in the app; pick one button shape convention for the replica rather than mixing both.

### 6b. Multi-tier bundle progress (`features/bundle/bundle.component.html`)

- Same page shell (back link, source URL) but shows **3 tiers in parallel**.
- **Shared phase card**: while scraping/review is running for all 3 tiers at once, a single wide card shows one combined progress bar + spinner + status text (avoids showing 3 identical bars).
- **Tier grid** (3 cards side by side, responsive): each card has a header (tier emoji icon + name + credit cost), then one of: "Queued" hint text (during shared phase), an individual progress bar + status (once tiers diverge), a "Ready" checkmark state with a "Full Preview" link (completed), or a red "✕ / Credit refunded" failed state. Selected/clickable/completed cards get distinct border-highlight classes.
- **All-done banner**: green-tinted strip once every tier resolves ("All versions ready — pick your favourite below!").
- **Preview section**: tab row (one tab per completed tier, icon + label, active-tab underline/highlight) above a large iframe preview panel (same loading-spinner-then-fade pattern as 6a), then action buttons (Full Preview outline, Download pill button with dynamic label: "Download (N cr)" / "Re-download" / spinner "Downloading…").
- This bundle view is the richer "progress" pattern — if the new project only needs one progress UI, prefer replicating this one since it demonstrates the shared-phase + per-item-divergence pattern, the tab-switchable multi-result preview, and the credit-cost-aware download button.

---

## 7. Cross-cutting patterns to standardize in the replica

- **Iframe preview pattern** (used identically in Progress single-view, Bundle view, and the full-screen Preview page): dark placeholder container → centered spinner + "Loading preview…" → iframe fades in via a `--visible` class once content is ready. Worth extracting as one shared `PreviewFrame` component.
- **Spinner**: small circular border-spin (`14–15px`, purple/white border-top accent) reused in buttons, progress cards, and preview loaders; a `--lg` (`28px`) variant for full-panel loading states.
- **Progress bar**: slim rounded track (`5–6px` tall, `#2a2a45` track) with a purple/gradient fill that transitions `width` smoothly — reused in History rows, single-generation progress, and bundle tier cards.
- **Card surface**: `#1a1a2e` background + `#2a2a45` 1px border + rounded corners (`12–16px`) is the standard "elevated panel" look, reused for history rows, progress cards, dropdowns, and tier cards.

---

## 8. Build order / verification

1. Scaffold the new project and set up the token file (Section 1 table) first.
2. Build the Header and Hero first — they establish the gradient/brand/button vocabulary the rest of the app reuses.
3. Build Welcome (login) next — reuses card + button + form-field patterns.
4. Build History and Progress last — they reuse badges, progress bars, and card surfaces already established.
5. Compare side-by-side against the live source app (`npm start` in `portal/`, default `http://localhost:4200`) for each section to confirm visual parity.
