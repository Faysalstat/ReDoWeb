# Angular UI Blueprint — ReeDo / ElevateWeb Design System

How to reproduce the UI of this React + Tailwind + shadcn app in an Angular application, pixel for pixel.

- **Source of truth:** this repo (`src/index.css`, `tailwind.config.js`, `src/components/**`)
- **Target:** Angular 17+ (standalone components, signals, built-in control flow `@if` / `@for`)
- **Assets:** every image, video, logo and icon the UI uses has been downloaded into **`ui-assets/`** in this repo, with a machine-readable map at **`ui-assets/manifest.json`**. See **§12** for what to copy and where.
- **Strategy:** keep **Tailwind CSS 3.4 and the same tokens**, so every class string in the React code can be copied into Angular templates unchanged. Only the component wiring changes (JSX → Angular templates, framer-motion → CSS + one directive, Radix → Angular CDK).

---

## 0. Design DNA (read this first)

| Trait | Rule |
|---|---|
| **Theme** | Dark only. `:root` and `.dark` hold identical values, so there is no light mode. |
| **Canvas** | Near-black blue-grey `#0d0e12`; cards `#14151a`. Surfaces are **translucent**: `bg-card/30`, `bg-card/50`, hover `bg-card/70`–`/80`. |
| **Brand color** | Violet `#735af2` (`--primary`). The signature gradient is `from-primary to-purple-500` (buttons, chat header, modals) and `from-purple-400 via-purple-500 to-blue-500` (hero headline text). |
| **Accent palette** | Each item in a feature grid gets its own neon accent: **cyan, purple, blue, orange, green, pink** (plus yellow for stars and warnings). An accent is always applied as a set: `text-{c}-400` icon + `bg-{c}-500/10` tile + `border-{c}-500/20…/40` edge. |
| **Conversion color** | **Green** (`green-400/500`) is the "go" color: URL form glow, the primary CTA when input is valid, success states, SEO links. **Orange-500** marks the "Recommended" badge and button. |
| **Borders** | Hairline and low contrast: `border-border/20` between sections, `/40` on cards, `/50` on chrome (nav, sidebar). |
| **Radius** | `--radius: 0.75rem`. Cards and panels use `rounded-2xl`, tiles and list rows `rounded-xl`, pills `rounded-full`, shadcn primitives `rounded-md`. |
| **Type** | Headings in **Poppins**, mostly at weight 900 (`font-black`); body in **Inter** 400 with relaxed leading (1.6–1.7). |
| **Rhythm** | Every landing section is `py-24 px-4 border-b border-border/20` with an inner `max-w-5xl mx-auto` and a centered `h2` with `mb-16`. |
| **Glass chrome** | Nav and headers are `bg-background/80–90 backdrop-blur-xl` with `border-border/50`. |
| **Motion** | Fade-up on enter (`opacity 0 → 1`, `y 20 → 0`), staggered by 60–100 ms per item; a pulsing green glow on the hero form; a marquee of logos; slowly drifting "mini website" cards in the page background at 12% opacity. |

---

## 1. Project setup

### 1.1 Dependencies

```bash
npm i -D tailwindcss@3.4 postcss autoprefixer tailwindcss-animate
npm i class-variance-authority clsx tailwind-merge@2.6 lucide-angular @angular/cdk ngx-sonner
```

> **Pin `tailwind-merge` to v2.x.** v3 only supports Tailwind v4, so it mis-merges some Tailwind 3 classes. The React app uses v3 with Tailwind 3, which is a latent bug in the source; don't copy it.

> **Why Tailwind 3.4 and not v4?** v4 renames and rescales utilities this design relies on (`shadow-sm`→`shadow-xs`, `rounded`/`blur` steps shift, `bg-gradient-to-*` → `bg-linear-to-*`, config moves to CSS). Staying on 3.4 lets you paste class strings 1:1. Migrate to v4 later as a separate step if you need to.

### 1.2 `tailwind.config.js`

Same as the React config, with three changes: Angular content globs, the accordion keyframes replaced (they depended on a Radix CSS variable), and the ad-hoc animations from the React components promoted into the theme.

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class'],
  content: ['./src/**/*.{html,ts}'],
  theme: {
    extend: {
      fontFamily: {
        inter: ['var(--font-inter)'],
        display: ['var(--font-display)'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
        popover: { DEFAULT: 'hsl(var(--popover))', foreground: 'hsl(var(--popover-foreground))' },
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary: { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        chart: {
          1: 'hsl(var(--chart-1))', 2: 'hsl(var(--chart-2))', 3: 'hsl(var(--chart-3))',
          4: 'hsl(var(--chart-4))', 5: 'hsl(var(--chart-5))',
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar-background))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))',
        },
      },
      keyframes: {
        'glow-flash': {
          '0%, 100%': { boxShadow: '0 0 40px 12px rgba(34,197,94,0.15), inset 0 0 20px rgba(34,197,94,0.08)' },
          '50%': { boxShadow: '0 0 60px 20px rgba(34,197,94,0.3), inset 0 0 30px rgba(34,197,94,0.15)' },
        },
        'blink-green': {
          '0%, 100%': { boxShadow: '0 0 15px rgba(34,197,94,0.5), inset 0 0 15px rgba(34,197,94,0.1)', borderColor: 'rgba(34,197,94,0.6)' },
          '50%': { boxShadow: '0 0 30px rgba(34,197,94,1), inset 0 0 30px rgba(34,197,94,0.3)', borderColor: 'rgba(34,197,94,1)' },
        },
        marquee: { from: { transform: 'translateX(0)' }, to: { transform: 'translateX(-50%)' } },
        'bar-sweep': { '0%, 100%': { width: '20%' }, '50%': { width: '90%' } },
      },
      animation: {
        'glow-flash': 'glow-flash 2s ease-in-out infinite',
        'blink-green': 'blink-green 1.5s infinite',
        marquee: 'marquee 30s linear infinite',
        'bar-sweep': 'bar-sweep 2s ease-in-out infinite',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
```

`postcss.config.js`:

```js
module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

### 1.3 `src/index.html`

```html
<!doctype html>
<html lang="en" class="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Poppins:wght@500;600;700;800;900&display=swap" rel="stylesheet" />
  <title>ElevateWeb — Transform Your Website in 60 Seconds With AI</title>
</head>
<body>
  <app-root></app-root>
</body>
</html>
```

(Loading the fonts with `<link>` is faster than the CSS `@import` the React app uses; the result looks the same.)

### 1.4 `src/styles.css` (global, copy verbatim)

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --font-inter: 'Inter', sans-serif;
    --font-display: 'Poppins', sans-serif;

    --background: 228 15% 6%;
    --foreground: 210 20% 95%;
    --card: 228 15% 9%;
    --card-foreground: 210 20% 95%;
    --popover: 228 15% 9%;
    --popover-foreground: 210 20% 95%;
    --primary: 250 85% 65%;
    --primary-foreground: 0 0% 100%;
    --secondary: 228 15% 14%;
    --secondary-foreground: 210 20% 85%;
    --muted: 228 12% 16%;
    --muted-foreground: 215 15% 55%;
    --accent: 250 85% 65%;
    --accent-foreground: 0 0% 100%;
    --destructive: 0 72% 51%;
    --destructive-foreground: 0 0% 100%;
    --border: 228 12% 16%;
    --input: 228 12% 16%;
    --ring: 250 85% 65%;
    --chart-1: 250 85% 65%;
    --chart-2: 180 65% 50%;
    --chart-3: 320 75% 55%;
    --chart-4: 45 90% 60%;
    --chart-5: 150 60% 50%;
    --radius: 0.75rem;
    --sidebar-background: 228 15% 8%;
    --sidebar-foreground: 210 20% 85%;
    --sidebar-primary: 250 85% 65%;
    --sidebar-primary-foreground: 0 0% 100%;
    --sidebar-accent: 228 15% 14%;
    --sidebar-accent-foreground: 210 20% 85%;
    --sidebar-border: 228 12% 16%;
    --sidebar-ring: 250 85% 65%;
  }
}

@layer base {
  * { @apply border-border outline-ring/50; }
  body {
    @apply bg-background text-foreground font-inter;
    font-weight: 400;
    line-height: 1.6;
  }
  h1, h2, h3, h4, h5, h6 { @apply font-display font-semibold; letter-spacing: -0.015em; }
  h1 { font-size: clamp(2.5rem, 5vw, 4rem); font-weight: 800; line-height: 1.1; }
  h2 { font-size: clamp(1.75rem, 4vw, 2.5rem); font-weight: 700; line-height: 1.2; }
  h3 { font-size: clamp(1.25rem, 3vw, 1.75rem); font-weight: 700; line-height: 1.3; }
  h4 { font-size: 1.125rem; font-weight: 600; line-height: 1.4; }
  p  { line-height: 1.7; letter-spacing: -0.003em; }
}

/* Utility classes used in templates */
.glow-flash { @apply animate-glow-flash; }

/* Scroll reveal: replaces framer-motion initial/animate/whileInView (see §5) */
.reveal {
  opacity: 0;
  transform: translate3d(0, var(--reveal-y, 20px), 0) scale(var(--reveal-scale, 1));
  transition: opacity .5s ease-out, transform .5s cubic-bezier(.22,1,.36,1);
  transition-delay: var(--reveal-delay, 0ms);
}
.reveal.is-visible { opacity: 1; transform: none; }

@media (prefers-reduced-motion: reduce) {
  .reveal { opacity: 1; transform: none; transition: none; }
  .animate-marquee, .animate-glow-flash, .animate-blink-green { animation: none; }
}
```

> The h1–h4 rules live in `@layer base`, so any Tailwind size class in a template (`text-4xl sm:text-6xl`) still wins over them. That is how the React app works too.

---

## 2. Design tokens reference

### 2.1 Semantic colors

| Token | HSL | Hex | Used for |
|---|---|---|---|
| `background` | 228 15% 6% | `#0d0e12` | page canvas |
| `foreground` | 210 20% 95% | `#f0f2f5` | body text |
| `card` / `popover` | 228 15% 9% | `#14151a` | surfaces (usually at /30–/80 alpha) |
| `primary` / `accent` / `ring` | 250 85% 65% | `#735af2` | brand violet, focus rings, active nav |
| `secondary` | 228 15% 14% | `#1e2029` | secondary buttons |
| `secondary-foreground` | 210 20% 85% | `#d1d9e0` | |
| `muted` / `border` / `input` | 228 12% 16% | `#24262e` | dividers, input borders, progress tracks |
| `muted-foreground` | 215 15% 55% | `#7b899d` | secondary text, captions, icons |
| `destructive` | 0 72% 51% | `#dc2828` | errors |
| `sidebar` | 228 15% 8% | `#111317` | dashboard sidebar |
| `chart-1…5` | violet / `#2dd2d2` / `#e236a9` / `#f5c73d` / `#33cc80` | | charts |

### 2.2 Accent palette (Tailwind defaults, not tokens)

| Accent | Icon / text | Tile bg | Border | Typical meaning |
|---|---|---|---|---|
| cyan | `text-cyan-400` | `bg-cyan-500/10` | `border-cyan-500/30`, hover `/50` | previews, featured plan |
| purple | `text-purple-400` | `bg-purple-500/10` | `border-purple-500/20` | AI, concepts, "all three" plan |
| blue | `text-blue-400` | `bg-blue-500/10` | `border-blue-500/20` | platforms, "analyzing" |
| orange | `text-orange-400` | `bg-orange-500/10` | `border-orange-500/20` | step numbers (`text-orange-400/70`), downloads, Recommended badge (`bg-orange-500`) |
| green | `text-green-400` | `bg-green-500/10` | `border-green-500/20` | success, SEO, price of free tier, checkmarks |
| pink | `text-pink-400` | `bg-pink-500/10` | `border-pink-500/20` | vault, awards |
| yellow | `text-yellow-400` | `bg-yellow-500/10` | `border-yellow-500/20` | stars, hero eyebrow, "pending", patience notices |
| red | `text-red-400` | `bg-red-500/10` | `border-red-500/20` | failed, X marks (`text-red-400/70`) |

Keep accent sets as **full literal class strings in TypeScript constants** (see `accents.ts` in §4.1). Never build them like `'text-' + color + '-400'`, because Tailwind's scanner can't see the result and the CSS is never generated.

### 2.3 Typography scale (as used)

| Role | Classes |
|---|---|
| Hero H1 | `text-4xl sm:text-6xl font-black mb-6 leading-tight` |
| Section H2 | `text-3xl sm:text-4xl font-black text-center mb-16` (use `mb-4` when a subtitle follows) |
| Section subtitle | `text-muted-foreground text-lg max-w-2xl mx-auto` (or plain `max-w-xl mx-auto`) |
| Eyebrow | `text-sm font-semibold text-primary uppercase tracking-wider block mb-4` |
| Micro label | `text-xs font-bold text-muted-foreground tracking-widest` (all caps copy) |
| Card title | `font-bold text-base mb-3` (or `mb-2` in horizontal cards) |
| Card body | `text-sm text-muted-foreground leading-relaxed` |
| Big number | `text-4xl font-black {accent}` |
| Dashboard page title | `font-display text-2xl font-bold mb-1` + `text-sm text-muted-foreground` |
| Gradient text | `bg-gradient-to-r from-purple-400 via-purple-500 to-blue-500 text-transparent bg-clip-text` |

### 2.4 Layout constants

| Element | Classes |
|---|---|
| Nav / footer container | `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8` |
| Section | `py-24 px-4 border-b border-border/20` (lighter sections use `py-20`, `border-t`) |
| Section inner | `max-w-5xl mx-auto` (FAQ `max-w-2xl`, comparison `max-w-4xl`, testimonials `max-w-6xl`) |
| Hero | `relative py-24 sm:py-40 px-4 text-center overflow-hidden border-b border-border/20`, inner `max-w-2xl mx-auto` |
| Grids | 4-up `grid sm:grid-cols-2 lg:grid-cols-4 gap-6`; 3-up `… lg:grid-cols-3 gap-6`; pricing `gap-8` |
| Nav height | `h-16` (fixed), so the public `<main>` gets `pt-16` |
| Dashboard | sidebar `w-60` fixed, content `lg:ml-60`, top bar `h-14`, page padding `p-4 sm:p-6 lg:p-8`, vertical stack `space-y-6` |
| Breakpoints | Tailwind defaults: `sm` 640, `md` 768 (nav collapses below), `lg` 1024 (sidebar collapses below) |

---

## 3. Angular architecture

```
src/app/
├── core/
│   └── auth.service.ts              # your existing auth; exposes isAuthenticated signal
├── shared/
│   ├── ui/                          # shadcn-equivalent primitives (directives)
│   │   ├── cn.ts
│   │   ├── button.directive.ts
│   │   ├── input.directive.ts       # uiInput + uiTextarea
│   │   ├── card.directives.ts       # uiCard, uiCardHeader, uiCardTitle, uiCardContent…
│   │   ├── badge.directive.ts
│   │   └── label.directive.ts
│   ├── motion/
│   │   ├── reveal.directive.ts      # fade-up on enter / in view
│   │   └── count-up.component.ts    # animated number counter
│   ├── design/
│   │   └── accents.ts               # literal accent class sets
│   └── components/                  # branded, reusable pattern components
│       ├── logo.component.ts
│       ├── section-header.component.ts
│       ├── icon-card.component.ts
│       ├── pricing-card.component.ts
│       ├── status-pill.component.ts
│       ├── score-ring.component.ts
│       ├── faq-accordion.component.ts
│       ├── logo-marquee.component.ts
│       ├── success-modal.component.ts
│       ├── chat-widget.component.ts
│       └── floating-websites-bg.component.ts
├── layouts/
│   ├── public-layout/ (navbar + footer + <router-outlet>)
│   ├── dashboard-layout/
│   └── auth-layout/
└── pages/ …
```

**Rule of thumb:** primitives are **attribute directives on native elements** (`<button uiButton>`, `<input uiInput>`), the way spartan/ui does it. That keeps native form behavior and accessibility, and lets you merge extra classes the same way React's `className` + `cn()` does.

> **Off-the-shelf alternative:** [spartan/ui](https://www.spartan.ng) is a shadcn port for Angular with the same token names and "new-york" look. If you'd rather not own the primitives, install its button/input/card/badge/dialog/accordion packages and skip §4.2. Everything else in this blueprint still applies.

### React → Angular translation table

| React (this repo) | Angular equivalent |
|---|---|
| `className={cn(a, b)}` | `class="…"` static + `[class]="expr"` (Ivy merges both); inside primitives use `cn()` |
| `` className={`… ${cond ? 'x' : 'y'}`} `` | `class="…" [class]="cond ? 'x' : 'y'"` |
| `{cond && <X/>}` / ternary | `@if (cond) { … } @else { … }` |
| `.map(item => …)` | `@for (item of items; track item.id) { … }` (`$index` for stagger) |
| `useState` | `signal()` ; derived values `computed()` |
| `useEffect` + cleanup | `constructor` / `ngOnInit` + `DestroyRef.onDestroy` or `afterNextRender` |
| `<Link to>` / `useLocation` | `routerLink` / `routerLinkActive` / `Router` |
| `<Outlet/>` | `<router-outlet />` |
| `lucide-react` `<Sparkles className/>` | `<lucide-icon [img]="Sparkles" class="…" />` (`lucide-angular`) |
| `framer-motion` enter / whileInView | `reveal` directive + CSS (§5) |
| `AnimatePresence` (mount/unmount) | CSS grid-rows trick or `@angular/animations` `:enter/:leave` (or `animate.enter` / `animate.leave` on Angular ≥ 20.2) |
| Radix Dialog / Popover / Tooltip | `@angular/cdk/dialog`, `@angular/cdk/overlay` |
| `sonner` toasts | `ngx-sonner` |
| React Query | your Angular data layer (`HttpClient` + signals / `resource()`) |

---

## 4. Shared foundation code

### 4.1 `cn.ts` and `accents.ts`

```ts
// shared/ui/cn.ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
```

```ts
// shared/design/accents.ts
export type Accent = 'cyan' | 'purple' | 'blue' | 'orange' | 'green' | 'pink' | 'yellow' | 'red';

export const ACCENTS: Record<Accent, { icon: string; tile: string; border: string; hoverBorder: string; soft: string }> = {
  cyan:   { icon: 'text-cyan-400',   tile: 'bg-cyan-500/10',   border: 'border-cyan-500/20',   hoverBorder: 'hover:border-cyan-500/40',   soft: 'bg-cyan-500/5' },
  purple: { icon: 'text-purple-400', tile: 'bg-purple-500/10', border: 'border-purple-500/20', hoverBorder: 'hover:border-purple-500/40', soft: 'bg-purple-500/5' },
  blue:   { icon: 'text-blue-400',   tile: 'bg-blue-500/10',   border: 'border-blue-500/20',   hoverBorder: 'hover:border-blue-500/40',   soft: 'bg-blue-500/5' },
  orange: { icon: 'text-orange-400', tile: 'bg-orange-500/10', border: 'border-orange-500/20', hoverBorder: 'hover:border-orange-500/40', soft: 'bg-orange-500/5' },
  green:  { icon: 'text-green-400',  tile: 'bg-green-500/10',  border: 'border-green-500/20',  hoverBorder: 'hover:border-green-500/40',  soft: 'bg-green-500/5' },
  pink:   { icon: 'text-pink-400',   tile: 'bg-pink-500/10',   border: 'border-pink-500/20',   hoverBorder: 'hover:border-pink-500/40',   soft: 'bg-pink-500/5' },
  yellow: { icon: 'text-yellow-400', tile: 'bg-yellow-500/10', border: 'border-yellow-500/20', hoverBorder: 'hover:border-yellow-500/40', soft: 'bg-yellow-500/5' },
  red:    { icon: 'text-red-400',    tile: 'bg-red-500/10',    border: 'border-red-500/20',    hoverBorder: 'hover:border-red-500/40',    soft: 'bg-red-500/5' },
};

/** Job / status pill colors (dashboard) */
export const STATUS_PILL: Record<string, string> = {
  pending:    'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  analyzing:  'bg-blue-500/10 text-blue-400 border-blue-500/20',
  generating: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  completed:  'bg-green-500/10 text-green-400 border-green-500/20',
  failed:     'bg-red-500/10 text-red-400 border-red-500/20',
};
```

### 4.2 Primitives (exact shadcn "new-york" classes)

```ts
// shared/ui/button.directive.ts
import { Directive, computed, input } from '@angular/core';
import { cva, type VariantProps } from 'class-variance-authority';
import type { ClassValue } from 'clsx';
import { cn } from './cn';

export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground shadow hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90',
        outline: 'border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground',
        secondary: 'bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-10 rounded-md px-8',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
);
type ButtonVariants = VariantProps<typeof buttonVariants>;

@Directive({
  selector: 'button[uiButton], a[uiButton]',
  standalone: true,
  host: { '[class]': 'computedClass()' },
})
export class UiButton {
  readonly variant = input<ButtonVariants['variant']>('default');
  readonly size = input<ButtonVariants['size']>('default');
  readonly userClass = input<ClassValue>('', { alias: 'class' });

  protected readonly computedClass = computed(() =>
    cn(buttonVariants({ variant: this.variant(), size: this.size() }), this.userClass()),
  );
}
```

Usage, mirroring `<Button size="lg" className="h-14 px-8 rounded-xl">`:

```html
<button uiButton size="lg" class="h-14 px-8 rounded-xl text-base font-bold">Upgrade My Website</button>
<a uiButton variant="outline" size="sm" routerLink="/dashboard">Dashboard</a>
```

Wrap the link itself (`<a uiButton routerLink>`), not a `<button>` inside an `<a>`. The React source nests buttons in links in several places; that's invalid HTML.

```ts
// shared/ui/input.directive.ts
import { Directive, computed, input } from '@angular/core';
import type { ClassValue } from 'clsx';
import { cn } from './cn';

@Directive({ selector: 'input[uiInput]', standalone: true, host: { '[class]': 'computedClass()' } })
export class UiInput {
  readonly userClass = input<ClassValue>('', { alias: 'class' });
  protected readonly computedClass = computed(() => cn(
    'flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm',
    this.userClass(),
  ));
}

@Directive({ selector: 'textarea[uiTextarea]', standalone: true, host: { '[class]': 'computedClass()' } })
export class UiTextarea {
  readonly userClass = input<ClassValue>('', { alias: 'class' });
  protected readonly computedClass = computed(() => cn(
    'flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm',
    this.userClass(),
  ));
}
```

```ts
// shared/ui/card.directives.ts — same pattern, one directive per part
import { Directive, computed, input } from '@angular/core';
import type { ClassValue } from 'clsx';
import { cn } from './cn';

/** Abstract base: subclasses only declare their base classes. Host binding is inherited. */
@Directive({ host: { '[class]': 'computedClass()' } })
export abstract class ClassMerge {
  protected abstract readonly base: string;
  readonly userClass = input<ClassValue>('', { alias: 'class' });
  // computed() is lazy, so the subclass's `base` is set before the first read
  protected readonly computedClass = computed(() => cn(this.base, this.userClass()));
}

@Directive({ selector: '[uiCard]', standalone: true })
export class UiCard extends ClassMerge { protected readonly base = 'rounded-xl border bg-card text-card-foreground shadow'; }
@Directive({ selector: '[uiCardHeader]', standalone: true })
export class UiCardHeader extends ClassMerge { protected readonly base = 'flex flex-col space-y-1.5 p-6'; }
@Directive({ selector: '[uiCardTitle]', standalone: true })
export class UiCardTitle extends ClassMerge { protected readonly base = 'font-semibold leading-none tracking-tight'; }
@Directive({ selector: '[uiCardDescription]', standalone: true })
export class UiCardDescription extends ClassMerge { protected readonly base = 'text-sm text-muted-foreground'; }
@Directive({ selector: '[uiCardContent]', standalone: true })
export class UiCardContent extends ClassMerge { protected readonly base = 'p-6 pt-0'; }
@Directive({ selector: '[uiCardFooter]', standalone: true })
export class UiCardFooter extends ClassMerge { protected readonly base = 'flex items-center p-6 pt-0'; }

export const UI_CARD = [UiCard, UiCardHeader, UiCardTitle, UiCardDescription, UiCardContent, UiCardFooter] as const;
```

`UiInput`, `UiTextarea`, `uiLabel` and any other fixed-class primitive can extend `ClassMerge` the same way.

```ts
// shared/ui/badge.directive.ts
export const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80',
        secondary: 'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
        destructive: 'border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80',
        outline: 'text-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);
// Directive: selector '[uiBadge]', same shape as UiButton with a single `variant` input.

// shared/ui/label.directive.ts — selector 'label[uiLabel]'
// base: 'text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70'
```

The other shadcn files in `src/components/ui/` (dialog, select, tabs, tooltip, etc.) follow the same principle: copy their class strings from the `.jsx` file, and use Angular CDK for the behavior.

---

## 5. Motion system

framer-motion is used for four things. Here is the Angular replacement for each.

### 5.1 Fade-up on enter and in view: `reveal` directive

```ts
// shared/motion/reveal.directive.ts
import { Directive, ElementRef, PLATFORM_ID, afterNextRender, inject, input, DestroyRef } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

/**
 * <div reveal>                     fade-up 20px when scrolled into view (whileInView, once)
 * <div reveal [revealDelay]="i*80">  staggered
 * <div reveal revealFrom="scale">  scale 0.9 → 1 (badges, pills, counters)
 */
@Directive({
  selector: '[reveal]',
  standalone: true,
  host: {
    class: 'reveal',
    '[style.--reveal-delay]': 'revealDelay() + "ms"',
    '[style.--reveal-y]': 'revealFrom() === "scale" ? "0px" : revealY() + "px"',
    '[style.--reveal-scale]': 'revealFrom() === "scale" ? 0.9 : 1',
  },
})
export class RevealDirective {
  readonly revealDelay = input(0);
  readonly revealY = input(20);
  readonly revealFrom = input<'up' | 'scale'>('up');

  constructor() {
    const el = inject(ElementRef<HTMLElement>).nativeElement;
    const destroyRef = inject(DestroyRef);
    if (!isPlatformBrowser(inject(PLATFORM_ID))) return;

    afterNextRender(() => {
      const io = new IntersectionObserver(([entry]) => {
        if (entry.isIntersecting) { el.classList.add('is-visible'); io.disconnect(); }
      }, { threshold: 0.15 });
      io.observe(el);
      destroyRef.onDestroy(() => io.disconnect());
    });
  }
}
```

Mapping of the timings used in the source:

| Source | Use |
|---|---|
| Grid items `delay: i * 0.1` / `0.08` / `0.06` | `[revealDelay]="$index * 100"` / `80` / `60` |
| Hero `y: 30` | `[revealY]="30"` |
| Mobile list rows `x: -10` | add an `--reveal-x` variant if you need it, or just use `up` |

### 5.2 Mount/unmount (mobile menu, FAQ answer, dropdowns): grid-rows trick

No JS animation library needed:

```html
<div class="grid transition-all duration-200 ease-out"
     [class]="open() ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'">
  <div class="overflow-hidden"> …content… </div>
</div>
```

For popups that scale in (chat panel, success modal), use `tailwindcss-animate` classes on mount:
`animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-4 duration-200`.

### 5.3 Continuous effects (pure CSS, already in config)

| Effect | Classes |
|---|---|
| Hero URL form glow | `glow-flash` (or `animate-blink-green` for the stronger variant) |
| Logo marquee | `animate-marquee w-max` on a doubled list |
| Live dot | `w-3 h-3 rounded-full bg-green-400 animate-pulse` |
| Spinners | `w-8 h-8 border-4 border-primary/20 border-t-primary rounded-full animate-spin` |
| Inline loader | `<lucide-icon [img]="Loader2" class="w-4 h-4 animate-spin" />` |
| Typing dots | three `w-2 h-2 bg-muted-foreground rounded-full animate-bounce`, delays 0 / .2s / .4s |
| Active stage bar | `h-full bg-primary rounded-full animate-bar-sweep` |

### 5.4 Animated counter

```ts
// shared/motion/count-up.component.ts
import { Component, ElementRef, afterNextRender, inject, input, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';

@Component({
  selector: 'app-count-up',
  standalone: true,
  imports: [DecimalPipe],
  template: `{{ value() | number }}{{ suffix() }}`,
})
export class CountUpComponent {
  readonly target = input.required<number>();
  readonly suffix = input('');
  readonly duration = input(2000);
  protected readonly value = signal(0);

  constructor() {
    const el = inject(ElementRef).nativeElement as HTMLElement;
    afterNextRender(() => {
      const io = new IntersectionObserver(([e]) => {
        if (!e.isIntersecting) return;
        io.disconnect();
        const start = performance.now();
        const tick = (now: number) => {
          const t = Math.min(1, (now - start) / this.duration());
          this.value.set(Math.floor(this.target() * t));
          if (t < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }, { threshold: 0.3 });
      io.observe(el);
    });
  }
}
```

---

## 6. Layout shells

### 6.1 Routes

```ts
export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./pages/auth/login.page') },
  { path: 'register', loadComponent: () => import('./pages/auth/register.page') },
  { path: 'forgot-password', loadComponent: () => import('./pages/auth/forgot-password.page') },
  { path: 'reset-password', loadComponent: () => import('./pages/auth/reset-password.page') },
  {
    path: '',
    loadComponent: () => import('./layouts/public-layout/public-layout.component'),
    children: [
      { path: '', loadComponent: () => import('./pages/home/home.page') },
      { path: 'pricing', loadComponent: () => import('./pages/pricing.page') },
      // scan, seo-growth, about, blog, careers, privacy, terms, checkout,
      // job/:jobId, job/:jobId/checkout, purchase-success/:purchaseId
    ],
  },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () => import('./layouts/dashboard-layout/dashboard-layout.component'),
    children: [
      { path: '', loadComponent: () => import('./pages/dashboard/overview.page') },
      { path: 'purchases', loadComponent: () => import('./pages/dashboard/purchases.page') },
      { path: 'growth', loadComponent: () => import('./pages/dashboard/growth.page') },
      { path: 'billing', loadComponent: () => import('./pages/dashboard/billing.page') },
    ],
  },
  { path: '**', loadComponent: () => import('./pages/not-found.page') },
];
```

(`loadComponent` with a bare `import()` needs each page to be the file's `default` export.)

Enable in-page anchors (`/#hero`, `/#contact`) and scroll-to-top:

```ts
provideRouter(routes, withInMemoryScrolling({ anchorScrolling: 'enabled', scrollPositionRestoration: 'top' }))
```

### 6.2 App root

```ts
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, FloatingWebsitesBgComponent, ChatWidgetComponent, NgxSonnerToaster],
  template: `
    <app-floating-websites-bg />
    <router-outlet />
    <ngx-sonner-toaster position="top-right" [richColors]="true" [closeButton]="true" theme="light" />
    <app-chat-widget />
  `,
})
export class AppComponent {}
```

> The source uses `theme="light"` toasts on a dark UI. That's what's live today, so it's kept here; switch to `theme="dark"` if you want them to match the rest of the UI.

Full-screen boot loader (shown while auth resolves):

```html
<div class="fixed inset-0 flex items-center justify-center bg-background">
  <div class="w-8 h-8 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
</div>
```

### 6.3 Public layout + Navbar

```ts
@Component({
  selector: 'app-public-layout',
  standalone: true,
  imports: [RouterOutlet, NavbarComponent, FooterComponent],
  template: `
    <div class="min-h-screen flex flex-col relative">
      <app-navbar />
      <main class="flex-1 pt-16 relative z-10"><router-outlet /></main>
      <app-footer class="relative z-10" />
    </div>
  `,
})
export default class PublicLayoutComponent {}
```

```html
<!-- navbar.component.html -->
<nav class="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/90 backdrop-blur-xl">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex items-center justify-between h-16">
      <a routerLink="/" class="flex items-center shrink-0"><app-logo size="md" /></a>

      <div class="hidden md:flex items-center gap-8">
        <a routerLink="/" fragment="hero" class="text-sm text-white hover:text-white/80 transition-colors">Redesign My Site</a>
        <a routerLink="/pricing" class="text-sm text-white hover:text-white/80 transition-colors">Pricing</a>
        <a routerLink="/seo-growth" class="text-sm text-green-400 hover:text-green-300 transition-colors font-semibold flex items-center gap-1">
          <lucide-icon [img]="icons.TrendingUp" class="w-4 h-4" />SEO Growth
        </a>
        <a routerLink="/" fragment="contact" class="text-sm text-white hover:text-white/80 transition-colors">Contact Us</a>
      </div>

      <div class="hidden md:flex items-center gap-3">
        @if (lastJobId() && !onJob()) {
          <a uiButton size="sm" variant="outline" [routerLink]="['/job', lastJobId()]"
             class="gap-1 border-primary/40 text-white hover:bg-primary/10 hover:text-white">
            View My Redesign <lucide-icon [img]="icons.ArrowRight" class="w-3 h-3" />
          </a>
        }
        @if (auth.isAuthenticated()) {
          <a uiButton size="sm" routerLink="/dashboard" class="hover:bg-primary/85 text-white">Dashboard</a>
        } @else {
          <a uiButton variant="ghost" size="sm" routerLink="/login" class="text-foreground hover:text-foreground hover:bg-muted">Sign In</a>
          <a uiButton size="sm" routerLink="/register" class="bg-primary hover:bg-primary/90 text-white">Get Started</a>
        }
      </div>

      <button class="md:hidden text-foreground p-1" (click)="open.set(!open())" [attr.aria-expanded]="open()" aria-label="Menu">
        <lucide-icon [img]="open() ? icons.X : icons.Menu" class="w-5 h-5" />
      </button>
    </div>
  </div>

  <!-- Mobile menu -->
  <div class="md:hidden grid transition-all duration-200"
       [class]="open() ? 'grid-rows-[1fr] opacity-100 border-t border-border/50' : 'grid-rows-[0fr] opacity-0'">
    <div class="overflow-hidden bg-background/95 backdrop-blur-xl">
      <div class="px-4 py-4 space-y-3" (click)="open.set(false)">
        <a routerLink="/" fragment="hero" class="block text-sm text-muted-foreground hover:text-foreground">Redesign My Site</a>
        <a routerLink="/pricing" class="block text-sm text-muted-foreground hover:text-foreground">Pricing</a>
        <a routerLink="/seo-growth" class="flex items-center gap-1 text-sm text-green-400 hover:text-green-300 font-semibold">
          <lucide-icon [img]="icons.TrendingUp" class="w-4 h-4" />SEO Growth
        </a>
        <a routerLink="/" fragment="contact" class="block text-sm text-muted-foreground hover:text-foreground">Contact Us</a>
        @if (auth.isAuthenticated()) {
          <a uiButton size="sm" routerLink="/dashboard" class="w-full bg-primary text-white">Dashboard</a>
        } @else {
          <div class="flex gap-2">
            <a uiButton variant="outline" size="sm" routerLink="/login" class="flex-1">Sign In</a>
            <a uiButton size="sm" routerLink="/register" class="flex-1 bg-primary text-white">Get Started</a>
          </div>
        }
      </div>
    </div>
  </div>
</nav>
```

```ts
// navbar.component.ts (essentials)
export class NavbarComponent {
  protected readonly icons = { TrendingUp, ArrowRight, Menu, X };
  protected readonly auth = inject(AuthService);
  protected readonly open = signal(false);
  private readonly url = toSignal(inject(Router).events.pipe(
    filter(e => e instanceof NavigationEnd), map(e => (e as NavigationEnd).urlAfterRedirects)), { initialValue: '' });
  protected readonly onJob = computed(() => this.url().startsWith('/job/'));
  protected readonly lastJobId = computed(() => { this.url(); return localStorage.getItem('reedo_last_job_id'); });
}
```

(Guard the `localStorage` call with `isPlatformBrowser` if you use SSR.)

### 6.4 Footer

```html
<footer class="border-t border-border/50 bg-background">
  <!-- "Trusted by" strip -->
  <div class="py-12">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <p class="text-center text-xs font-bold text-muted-foreground mb-8 tracking-widest">TRUSTED BY LEADING COMPANIES</p>
      <div class="flex flex-wrap items-center justify-center gap-8 sm:gap-12 md:gap-16 lg:gap-20">
        @for (logo of trustedLogos; track logo.alt) {
          <div class="h-14 flex items-center">
            <img [src]="logo.src" [alt]="logo.alt" class="h-full object-contain opacity-75 hover:opacity-100 transition-opacity" />
          </div>
        }
      </div>
    </div>
  </div>

  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <div class="grid grid-cols-2 md:grid-cols-4 gap-8">
      <div class="col-span-2 md:col-span-1">
        <a routerLink="/" class="flex items-center gap-2 mb-4">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-400 flex items-center justify-center">
            <lucide-icon [img]="icons.Sparkles" class="w-4 h-4 text-white" />
          </div>
          <span class="font-display font-bold text-lg">ReeDo</span>
        </a>
        <p class="text-sm text-muted-foreground leading-relaxed">Transform your website in 60 seconds with AI. Modern redesigns without agency pricing.</p>
      </div>
      @for (col of columns; track col.title) {
        <div>
          <h4 class="font-semibold text-sm mb-4">{{ col.title }}</h4>
          <div class="space-y-2">
            @for (l of col.links; track l.label) {
              <a [routerLink]="l.path" [fragment]="l.fragment" class="block text-sm text-muted-foreground hover:text-foreground transition-colors">{{ l.label }}</a>
            }
          </div>
        </div>
      }
    </div>
  </div>

  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="border-t border-border/50 pt-6 flex flex-col sm:flex-row justify-between items-center gap-4">
      <p class="text-xs text-muted-foreground">© 2026 ReeDo. All rights reserved.</p>
      <p class="text-xs text-muted-foreground">Made with AI. Built for business owners.</p>
    </div>
  </div>
</footer>
```

```ts
protected readonly trustedLogos = [
  { alt: 'Google',    src: '/assets/logos/trusted/google.png' },
  { alt: 'Amazon',    src: '/assets/logos/trusted/amazon.svg' },
  { alt: 'Microsoft', src: '/assets/logos/trusted/microsoft.svg' },
  { alt: 'Figma',     src: '/assets/logos/trusted/figma.svg' },
  { alt: 'Adobe',     src: '/assets/logos/trusted/adobe.ico' },
  { alt: 'Slack',     src: '/assets/logos/trusted/slack.ico' },
];
```

Columns: **Product** (Pricing, Features `/#features`, How It Works `/#how-it-works`), **Company** (About, Blog, Careers), **Legal** (Privacy, Terms, Contact `/#contact`).

### 6.5 Dashboard layout

```html
<div class="min-h-screen bg-background flex">
  <!-- Desktop sidebar -->
  <aside class="hidden lg:flex w-60 border-r border-border/50 bg-card/30 flex-col fixed inset-y-0">
    <ng-container *ngTemplateOutlet="sidebar" />
  </aside>

  <!-- Mobile drawer -->
  @if (sidebarOpen()) {
    <div class="fixed inset-0 z-50 lg:hidden">
      <div class="absolute inset-0 bg-black/50 animate-in fade-in-0" (click)="sidebarOpen.set(false)"></div>
      <aside class="relative w-60 bg-card border-r border-border/50 h-full animate-in slide-in-from-left duration-200">
        <ng-container *ngTemplateOutlet="sidebar" />
      </aside>
    </div>
  }

  <div class="flex-1 lg:ml-60">
    <header class="sticky top-0 z-40 h-14 border-b border-border/50 bg-background/80 backdrop-blur-xl flex items-center px-4 gap-4">
      <button class="lg:hidden" (click)="sidebarOpen.set(true)" aria-label="Open menu"><lucide-icon [img]="icons.Menu" class="w-5 h-5" /></button>
      <div class="flex-1"></div>
      <a uiButton size="sm" routerLink="/scan" class="bg-primary hover:bg-primary/90 text-xs">
        <lucide-icon [img]="icons.Sparkles" class="w-3 h-3 mr-1" /> New Scan
      </a>
    </header>
    <main class="flex flex-col">
      <div class="flex-1 p-4 sm:p-6 lg:p-8"><router-outlet /></div>
      <app-contact-section />
    </main>
  </div>
</div>

<ng-template #sidebar>
  <div class="flex flex-col h-full">
    <div class="p-4 border-b border-border/50">
      <a routerLink="/" class="flex items-center gap-2">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-400 flex items-center justify-center">
          <lucide-icon [img]="icons.Sparkles" class="w-4 h-4 text-white" />
        </div>
        <span class="font-display font-bold text-lg">ElevateWeb</span>
      </a>
    </div>
    <nav class="flex-1 p-3 space-y-1">
      @for (item of navItems; track item.path) {
        <a [routerLink]="item.path" routerLinkActive #rla="routerLinkActive" [routerLinkActiveOptions]="{ exact: true }"
           (click)="sidebarOpen.set(false)"
           class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all"
           [class]="rla.isActive ? 'bg-primary/10 text-primary font-medium' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'">
          <lucide-icon [img]="item.icon" class="w-4 h-4" /> {{ item.label }}
        </a>
      }
    </nav>
    <div class="p-3 border-t border-border/50">
      <button (click)="logout()" class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 w-full transition-colors">
        <lucide-icon [img]="icons.LogOut" class="w-4 h-4" /> Sign Out
      </button>
    </div>
  </div>
</ng-template>
```

Nav items: Overview `/dashboard` (LayoutDashboard), My Purchases `/dashboard/purchases` (ShoppingBag), SEO Growth `/dashboard/growth` (TrendingUp), Billing `/dashboard/billing` (CreditCard).

> Use `#rla` with a ternary `[class]` instead of passing classes to `routerLinkActive` directly. Otherwise the inactive `text-muted-foreground` and the active `text-primary` both end up on the element and CSS order decides which one wins.

### 6.6 Auth layout (login / register / forgot / reset)

```ts
@Component({
  selector: 'app-auth-layout',
  standalone: true,
  imports: [LucideAngularModule],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-background px-4">
      <div class="w-full max-w-md">
        <div class="text-center mb-10">
          <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary mb-4">
            <lucide-icon [img]="icon()" class="w-7 h-7 text-primary-foreground" aria-hidden="true" />
          </div>
          <h1 class="text-3xl font-bold tracking-tight text-foreground">{{ title() }}</h1>
          @if (subtitle()) { <p class="text-muted-foreground mt-2">{{ subtitle() }}</p> }
        </div>
        <div class="bg-card rounded-2xl shadow-sm border border-border p-8"><ng-content /></div>
        <p class="text-center text-sm text-muted-foreground mt-6"><ng-content select="[authFooter]" /></p>
      </div>
    </div>`,
})
export class AuthLayoutComponent {
  readonly icon = input.required<LucideIconData>();
  readonly title = input.required<string>();
  readonly subtitle = input<string>();
}
```

Login form body, the pattern every auth page reuses:

```html
<app-auth-layout [icon]="icons.LogIn" title="Welcome back" subtitle="Log in to your account">
  <button uiButton variant="outline" class="w-full h-12 text-sm font-medium mb-6" (click)="google()">
    <app-google-icon class="w-5 h-5 mr-2" /> Continue with Google
  </button>

  <div class="relative mb-6">
    <div class="absolute inset-0 flex items-center"><div class="w-full border-t border-border"></div></div>
    <div class="relative flex justify-center text-xs uppercase"><span class="bg-card px-3 text-muted-foreground">or</span></div>
  </div>

  @if (error()) { <div class="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">{{ error() }}</div> }

  <form [formGroup]="form" (ngSubmit)="submit()" class="space-y-4">
    <div class="space-y-2">
      <label uiLabel for="email">Email</label>
      <div class="relative">
        <lucide-icon [img]="icons.Mail" class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input uiInput id="email" type="email" formControlName="email" placeholder="you@example.com" class="pl-10 h-12" />
      </div>
    </div>
    <div class="space-y-2">
      <div class="flex items-center justify-between">
        <label uiLabel for="password">Password</label>
        <a routerLink="/forgot-password" class="text-xs text-primary hover:underline">Forgot password?</a>
      </div>
      <div class="relative">
        <lucide-icon [img]="icons.Lock" class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input uiInput id="password" type="password" formControlName="password" placeholder="••••••••" class="pl-10 h-12" />
      </div>
    </div>
    <button uiButton type="submit" class="w-full h-12 font-medium" [disabled]="loading()">
      @if (loading()) { <lucide-icon [img]="icons.Loader2" class="w-4 h-4 mr-2 animate-spin" /> Logging in... } @else { Log in }
    </button>
  </form>

  <span authFooter>Don't have an account? <a routerLink="/register" class="text-primary font-medium hover:underline">Create one</a></span>
</app-auth-layout>
```

---

## 7. Pattern library (branded components)

Each pattern lists the exact classes from the React source. Build them once in `shared/components` and reuse.

### 7.1 Logo

Red circle with a serif "R", then the wordmark **R**ee**D**o (R red, D green).

```ts
@Component({
  selector: 'app-logo',
  standalone: true,
  template: `
    <div class="inline-flex items-center" [style.gap.px]="8 * s()">
      <div class="flex items-center justify-center shrink-0 rounded-full"
           [style.width.px]="34 * s()" [style.height.px]="34 * s()"
           style="background:#E52222; box-shadow:0 2px 8px rgba(229,34,34,.45)">
        <span style="color:#fff;font-weight:900;line-height:1;font-family:Georgia,serif;letter-spacing:-.02em" [style.font-size.px]="22 * s()">R</span>
      </div>
      <span class="flex items-baseline" style="font-family:Georgia,'Times New Roman',serif;letter-spacing:-.01em;line-height:1" [style.font-size.px]="22 * s()">
        <span style="color:#E52222;font-weight:900">R</span><span class="text-foreground font-bold">ee</span><span style="color:#22C55E;font-weight:900">D</span><span class="text-foreground font-bold">o</span>
      </span>
    </div>`,
})
export class LogoComponent {
  readonly size = input<'sm' | 'md' | 'lg'>('md');
  protected readonly s = computed(() => ({ sm: 0.75, md: 1, lg: 1.4 })[this.size()]);
}
```

Secondary mark (footer, sidebar): `w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-400` tile with a white Sparkles icon, plus `font-display font-bold text-lg` text.

### 7.2 Hero with URL form

```html
<section id="hero" class="relative py-24 sm:py-40 px-4 text-center overflow-hidden border-b border-border/20">
  <div reveal [revealY]="30" class="w-full max-w-2xl mx-auto">
    <div class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-sm font-semibold mb-8">
      <lucide-icon [img]="icons.Sparkles" class="w-4 h-4" /> AI Website Redesign Engine
    </div>
    <h1 class="text-4xl sm:text-6xl font-black mb-6 leading-tight">
      Your Website, <span class="bg-gradient-to-r from-purple-400 via-purple-500 to-blue-500 text-transparent bg-clip-text">Redesigned by AI</span> in 15 Minutes
    </h1>
    <p class="text-muted-foreground text-lg mb-12 max-w-2xl mx-auto leading-relaxed">
      Paste your website URL, choose a style, and instantly see a modern redesign preview powered by AI. No designers needed.
    </p>

    <form (submit)="$event.preventDefault(); scan()"
          class="flex flex-col sm:flex-row gap-3 mb-8 p-6 rounded-2xl border-2 border-green-400 bg-green-500/5 backdrop-blur-sm glow-flash">
      <div class="relative flex-1">
        <lucide-icon [img]="icons.Globe" class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <input uiInput [value]="url()" (input)="url.set($any($event.target).value)" [disabled]="loading()"
               placeholder="https://yourbusiness.com"
               class="pl-12 h-14 text-base rounded-xl border-0 bg-transparent text-foreground placeholder:text-muted-foreground" />
      </div>
      <button uiButton type="submit" size="lg" [disabled]="loading() || !url().trim()"
              class="h-14 px-8 rounded-xl text-base font-bold transition-colors whitespace-nowrap"
              [class]="url().trim() ? 'bg-green-500 hover:bg-green-600 active:bg-green-700' : 'bg-primary hover:bg-primary/90'">
        @if (loading()) { <lucide-icon [img]="icons.Loader2" class="w-5 h-5 mr-2 animate-spin" /> Analyzing... }
        @else { Upgrade My Website <lucide-icon [img]="icons.ArrowRight" class="w-5 h-5 ml-2" /> }
      </button>
    </form>

    <div class="flex flex-wrap justify-center gap-6 text-sm text-muted-foreground">
      <span class="flex items-center gap-2"><lucide-icon [img]="icons.Zap" class="w-4 h-4 text-primary" /> 3 unique designs</span>
      <span class="flex items-center gap-2"><lucide-icon [img]="icons.Shield" class="w-4 h-4 text-green-400" /> No payment until you choose</span>
      <span class="flex items-center gap-2"><lucide-icon [img]="icons.Sparkles" class="w-4 h-4 text-purple-400" /> Live previews</span>
    </div>
  </div>
</section>
```

Signature behavior: **the CTA turns from violet to green as soon as the input has text.** Reuse that on other "submit" forms (the contact form does the same once the message is ≥ 5 characters).

Alternative hero (`landing/HeroSection.jsx`): three blurred glow blobs behind the content:

```html
<div class="absolute inset-0 pointer-events-none">
  <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-primary/10 rounded-full blur-[120px]"></div>
  <div class="absolute top-40 left-1/4 w-[400px] h-[400px] bg-purple-500/[0.08] rounded-full blur-[100px]"></div>
  <div class="absolute top-60 right-1/4 w-[300px] h-[300px] bg-blue-500/[0.08] rounded-full blur-[80px]"></div>
</div>
```

(The source writes `bg-purple-500/8`, which isn't in Tailwind 3's default opacity scale and silently produces no CSS. `/[0.08]` gives the intended result.)

### 7.3 Section header

```ts
@Component({
  selector: 'app-section-header',
  standalone: true,
  imports: [RevealDirective],
  host: { class: 'block' },
  template: `
    <div reveal class="text-center" [class]="subtitle() ? 'mb-16' : ''">
      @if (eyebrow()) { <span class="text-sm font-semibold text-primary uppercase tracking-wider block mb-4">{{ eyebrow() }}</span> }
      <h2 class="text-3xl sm:text-4xl font-black" [class]="subtitle() ? 'mb-4' : 'mb-16'">{{ title() }}</h2>
      @if (subtitle()) { <p class="text-muted-foreground max-w-xl mx-auto">{{ subtitle() }}</p> }
    </div>`,
})
export class SectionHeaderComponent {
  readonly eyebrow = input<string>();
  readonly title = input.required<string>();
  readonly subtitle = input<string>();
}
```

Section wrapper, used everywhere:

```html
<section class="py-24 px-4 border-b border-border/20">
  <div class="max-w-5xl mx-auto">
    <app-section-header eyebrow="Why ReeDo" title="The Smarter Way to Redesign" subtitle="Skip the agencies…" />
    …grid…
  </div>
</section>
```

### 7.4 Cards

**Step card** (How It Works)

```html
<div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
  @for (s of steps; track s.step) {
    <div reveal [revealDelay]="$index * 100" class="p-6 rounded-2xl border border-border/40 bg-card/50 hover:bg-card/70 transition-colors">
      <div class="text-4xl font-black text-orange-400/70 mb-4">{{ s.step }}</div>
      <h3 class="font-bold text-base mb-3">{{ s.title }}</h3>
      <p class="text-sm text-muted-foreground leading-relaxed">{{ s.desc }}</p>
    </div>
  }
</div>
```

**Icon feature card** (vertical; "Everything You Need")

```html
@for (f of features; track f.title) {
  <div reveal [revealDelay]="$index * 80"
       class="p-6 rounded-2xl border border-border/40 bg-card/50 hover:bg-card/70 transition-colors"
       [class]="accents[f.accent].hoverBorder">
    <div class="w-12 h-12 rounded-xl flex items-center justify-center mb-4" [class]="accents[f.accent].tile">
      <lucide-icon [img]="f.icon" class="w-6 h-6" [class]="accents[f.accent].icon" />
    </div>
    <h3 class="font-bold text-base mb-3">{{ f.title }}</h3>
    <p class="text-sm text-muted-foreground leading-relaxed">{{ f.desc }}</p>
  </div>
}
```

Feature accent order: cyan, purple, blue, orange, green, pink.

**Horizontal icon card** ("Why Choose Us", 2-up): `flex gap-5 p-6 rounded-2xl border {accent.border} bg-card/50 hover:bg-card/80 transition-colors`, with the icon tile `shrink-0`, then `h3 mb-2` and text.

**Stat tile**: `text-center p-6 rounded-2xl border border-border/40 bg-card/30`, number `text-4xl font-black {accent} mb-1` wrapping `<app-count-up [target]="12847" suffix="+" />`, label `text-sm text-muted-foreground`.

**Trust badge**: `text-center p-6 rounded-2xl border border-border/40 bg-background/50`, icon `w-8 h-8 mx-auto mb-3 {accent}`, title `font-bold text-sm mb-1`, body `text-xs text-muted-foreground`. The section has an extra `bg-card/20`.

**Contact info card**: `flex flex-col items-center p-6 rounded-2xl border {c}-500/30 hover:{c}-500/50 bg-{c}-500/5 transition-all`, icon `w-6 h-6 mb-3`, label `text-sm text-muted-foreground mb-2`, value `font-semibold`.

**Testimonial card**: `p-6 rounded-2xl border border-border/40 bg-card/30`; 5× star `w-4 h-4 fill-yellow-400 text-yellow-400` in `flex gap-1 mb-4`; quote `text-muted-foreground mb-4 italic`; author row `flex items-center gap-3`, avatar `w-10 h-10 rounded-full object-cover`, name `font-semibold text-sm`, role `text-xs text-muted-foreground`.

**Dashboard stat card**: `uiCard class="bg-card/50 border-border/50"` → `uiCardContent class="p-5 flex items-center gap-4"`, tile `w-10 h-10 rounded-xl bg-primary/10` with icon `w-5 h-5 text-primary`, label `text-xs text-muted-foreground`, value `font-display text-xl font-bold`.

**Report metric tile** (modals): `p-3 rounded-lg bg-{c}-500/10 border border-{c}-500/20`, label `text-xs text-muted-foreground`, value `text-xl font-bold text-{c}-400`.

### 7.5 Pricing cards (home variant)

```ts
export interface Plan {
  name: string; price: string; desc: string; features: string[];
  priceColor: string; borderClass: string; highlight?: boolean; badge?: string; buttonText?: string;
}
export const PLANS: Plan[] = [
  { name: 'Free Preview', price: '$0', desc: 'Browse your AI redesign for free',
    features: ['Live interactive preview', 'All pages included', 'No credit card needed', 'No downloads'],
    priceColor: 'text-green-400', borderClass: 'border-green-500/40 bg-green-500/5', buttonText: 'Start Redesign' },
  { name: 'Premium Redesign', price: '$59.95', highlight: true, badge: 'Recommended', desc: 'Complete award-worthy website redesign',
    features: ['Full redesigned website', 'All pages generated', 'Platform-specific files', 'Lifetime downloads', 'Email delivery'],
    priceColor: 'text-cyan-400', borderClass: 'border-cyan-500/50 bg-cyan-500/5' },
  { name: 'All Three Designs', price: '$79.95', desc: 'Get all 3 unique redesign concepts',
    features: ['All 3 design variations', 'All pages generated', 'Platform-specific files', 'Lifetime downloads', 'Email delivery', 'Best value'],
    priceColor: 'text-purple-400', borderClass: 'border-purple-500/40 bg-purple-500/5' },
];
```

```html
<div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-8">
  @for (plan of plans; track plan.name) {
    <div class="p-8 rounded-2xl border-2 text-left relative flex flex-col" [class]="plan.borderClass">
      @if (plan.badge) {
        <span class="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-orange-500 text-white text-xs font-bold">{{ plan.badge }}</span>
      }
      <p class="text-xs text-muted-foreground mb-2 font-semibold uppercase tracking-wider">{{ plan.name }}</p>
      <p class="text-4xl font-black mb-3" [class]="plan.priceColor">{{ plan.price }}</p>
      <p class="text-sm text-muted-foreground mb-8">{{ plan.desc }}</p>
      <ul class="space-y-3 mb-10 flex-1">
        @for (f of plan.features; track f) {
          <li class="flex items-start gap-3 text-sm">
            <lucide-icon [img]="icons.Check" class="w-4 h-4 flex-shrink-0 mt-0.5 text-green-400" /><span>{{ f }}</span>
          </li>
        }
      </ul>
      <a uiButton routerLink="/" fragment="hero" [variant]="plan.highlight ? 'default' : 'outline'" class="w-full"
         [class]="plan.highlight ? 'bg-orange-500 hover:bg-orange-600 text-white' : 'border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10'">
        {{ plan.buttonText ?? 'Get Started' }} <lucide-icon [img]="icons.ArrowRight" class="w-4 h-4 ml-2" />
      </a>
    </div>
  }
</div>
<p class="text-sm text-muted-foreground mt-8">
  + SEO Growth Add-on available at checkout — <span class="line-through">$29.95</span>
  <span class="text-green-400 font-semibold">$19.95/mo</span>
</p>
```

**Pricing page variant** (`pricing/PricingCard.jsx`):
- featured: `relative rounded-2xl border p-6 sm:p-8 border-primary/40 bg-gradient-to-b from-primary/5 to-card shadow-xl shadow-primary/10`, with badge `uiBadge class="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-primary to-purple-500 text-white border-0"` (Sparkles + "Most Popular")
- normal: `border-border/50 bg-card/50`
- CTA: `w-full rounded-xl mb-6`, featured `bg-gradient-to-r from-primary to-purple-500 hover:from-primary/90 hover:to-purple-500/90 shadow-lg shadow-primary/25`, otherwise `bg-secondary hover:bg-secondary/80 text-foreground`
- price `font-display text-4xl font-bold` + period `text-muted-foreground mb-1`; checks `text-primary`.

### 7.6 Pills, badges, status

| Pattern | Classes |
|---|---|
| Eyebrow pill (yellow) | `inline-flex items-center gap-2 px-4 py-2 rounded-full bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-sm font-semibold` |
| Eyebrow pill (primary) | `inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-primary/30 bg-primary/5` + `text-xs font-medium text-primary` |
| Platform chip | `px-5 py-2.5 rounded-full border border-border/40 bg-card/40 hover:bg-card/80 transition-all duration-200` + `text-sm font-semibold` with `[style.color]="p.color"` (brand hex) |
| Highlight chip in table head | `text-sm font-black text-primary bg-primary/10 px-3 py-1 rounded-full` |
| Status pill | `text-xs px-2 py-0.5 rounded-full border font-medium` + `STATUS_PILL[status]`, with a spinning Loader2 for `analyzing`/`generating` |
| Notice banner | `flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-yellow-400/30 bg-yellow-400/5 text-yellow-300 text-sm font-medium` |
| Error box | `p-3 rounded-lg bg-destructive/10 text-destructive text-sm` |
| Success banner (dashboard) | `uiCard class="bg-gradient-to-r from-primary/10 to-purple-500/5 border-primary/20"` |

### 7.7 FAQ accordion

```html
<section class="py-20 px-4 border-t border-border/20">
  <div class="max-w-2xl mx-auto">
    <h2 class="text-3xl sm:text-4xl font-black text-center mb-4">Frequently Asked Questions</h2>
    <p class="text-center text-muted-foreground mb-12">Got questions? We've got answers.</p>
    <div class="space-y-3">
      @for (faq of faqs; track faq.q; let i = $index) {
        <div reveal [revealDelay]="i * 50" [revealY]="10">
          <button (click)="open.set(open() === i ? -1 : i)" [attr.aria-expanded]="open() === i"
                  class="w-full flex items-center justify-between p-5 rounded-xl border border-border/40 bg-card/30 hover:bg-card/60 transition-colors text-left">
            <span class="font-semibold">{{ faq.q }}</span>
            <lucide-icon [img]="icons.ChevronDown" class="w-5 h-5 text-primary transition-transform" [class]="open() === i ? 'rotate-180' : ''" />
          </button>
          <div class="grid transition-all duration-200" [class]="open() === i ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'">
            <div class="overflow-hidden">
              <div class="p-5 border border-t-0 border-border/40 rounded-b-xl bg-card/20">
                <p class="text-muted-foreground">{{ faq.a }}</p>
              </div>
            </div>
          </div>
        </div>
      }
    </div>
  </div>
</section>
```

`open = signal(0)`, so the first item starts expanded.

### 7.8 Comparison table

The table is a `grid grid-cols-4` layout, not a `<table>`:
- wrapper `rounded-2xl border border-border/40 overflow-hidden`
- head row `grid grid-cols-4 bg-card/80 border-b border-border/40`, cells `p-4 text-sm font-semibold text-muted-foreground`, own column with the highlight chip `ReeDo ✦`
- body rows `grid grid-cols-4 border-b border-border/20 last:border-0`, zebra `bg-card/20` on even rows (`[class]="$even ? 'bg-card/20' : 'bg-transparent'"`)
- own column `text-cyan-400`, others `text-foreground/70`
- cell values: `true` → Check `w-5 h-5 text-green-400 mx-auto`; `false` → X `w-5 h-5 text-red-400/70 mx-auto`; `null` → Minus `w-4 h-4 text-muted-foreground mx-auto`; strings → `text-sm font-semibold`.

### 7.9 Live counter bar and logo marquee

```html
<!-- Live counter -->
<section class="py-12 px-4 border-b border-border/20 bg-primary/5">
  <div class="max-w-5xl mx-auto flex flex-wrap items-center justify-center gap-8 text-center">
    <div reveal revealFrom="scale" class="flex items-center gap-3">
      <div class="w-3 h-3 rounded-full bg-green-400 animate-pulse"></div>
      <span class="text-sm text-muted-foreground"><span class="text-foreground font-bold text-lg">{{ today() }}</span> websites redesigned today</span>
    </div>
    <div class="w-px h-6 bg-border/40 hidden sm:block"></div>
    <!-- repeat: Globe cyan "total redesigns", Star yellow "4.9/5 average rating", Users purple "2,300+ happy customers" -->
  </div>
</section>

<!-- Marquee -->
<div class="py-8 border-y border-border/20 overflow-hidden bg-card/10">
  <p class="text-center text-xs text-muted-foreground uppercase tracking-widest mb-6 font-medium">As featured in &amp; trusted by businesses using</p>
  <div class="relative">
    <div class="absolute left-0 top-0 bottom-0 w-24 bg-gradient-to-r from-background to-transparent z-10 pointer-events-none"></div>
    <div class="absolute right-0 top-0 bottom-0 w-24 bg-gradient-to-l from-background to-transparent z-10 pointer-events-none"></div>
    <div class="flex gap-12 items-center animate-marquee w-max">
      @for (b of brandsDoubled; track $index) {
        <span class="text-lg whitespace-nowrap select-none" [class]="b.style">{{ b.name }}</span>
      }
    </div>
  </div>
</div>
```

`brandsDoubled = [...BRANDS, ...BRANDS]`, so the -50% translate loops without a seam. Brand styles are literal strings such as `'font-serif font-black tracking-tight text-white/70'` and `'font-sans font-black text-green-400/70'`.

### 7.10 Forms (contact, email capture)

- Panel: `p-8 rounded-2xl border border-border/50 bg-card/50`, fields `space-y-4`, label `block text-sm font-medium mb-2`, input `uiInput class="bg-background/50"`.
- Textarea: `uiTextarea rows="5" class="px-4 py-2 rounded-lg bg-background/50"`.
- Submit: `w-full rounded-lg transition-all duration-300`, gradient `bg-gradient-to-r from-primary to-purple-500 hover:from-primary/90 hover:to-purple-500/90`, switching to `bg-green-500 hover:bg-green-600 text-white` once the form is valid.
- Email capture section: `bg-gradient-to-br from-primary/5 to-purple-900/10`, icon tile `w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20`, input with an orange focus look `bg-background/60 border-orange-500 ring-1 ring-orange-500`, success line `text-green-400 font-semibold` with a Check icon.

### 7.11 Success modal

Use `@angular/cdk/dialog` for focus trapping and Esc handling, with these classes:

```ts
this.dialog.open(SuccessModalComponent, {
  backdropClass: ['bg-black/60', 'backdrop-blur-sm'],
  panelClass: ['w-full', 'max-w-md', 'px-4'],
});
```

```html
<div class="relative bg-card border border-border rounded-2xl p-8 w-full text-center shadow-2xl animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-4 duration-200">
  <button (click)="close()" class="absolute top-4 right-4 text-muted-foreground hover:text-foreground transition-colors" aria-label="Close">
    <lucide-icon [img]="icons.X" class="w-5 h-5" />
  </button>
  <div class="flex justify-center mb-4">
    <div class="w-16 h-16 rounded-full bg-green-500/15 flex items-center justify-center">
      <lucide-icon [img]="icons.CheckCircle" class="w-8 h-8 text-green-400" />
    </div>
  </div>
  <h3 class="text-xl font-bold mb-2">Message Sent Successfully!</h3>
  <p class="text-muted-foreground text-sm leading-relaxed mb-6">…</p>
  <button uiButton class="w-full bg-gradient-to-r from-primary to-purple-500 hover:from-primary/90 hover:to-purple-500/90" (click)="close()">Close</button>
</div>
```

Add `@import '@angular/cdk/overlay-prebuilt.css';` to `styles.css` (before the `@tailwind` lines) when you use CDK overlays.

### 7.12 Processing progress (multi-stage loader)

- Ring loader: `relative w-14 h-14`, track `absolute inset-0 rounded-full border-4 border-primary/20`, spinner `absolute inset-0 rounded-full border-4 border-t-primary animate-spin` (the source paints all four borders, so only the `border-t-primary` colour change is visible), centered `text-xs font-bold text-primary` percentage.
- Overall bar: track `w-full h-2.5 bg-muted rounded-full overflow-hidden`, fill `h-full rounded-full bg-gradient-to-r from-primary to-purple-400 transition-[width] duration-700 ease-out` with `[style.width.%]="pct()"`.
- Stage row: `flex items-center gap-4 p-4 rounded-xl border transition-all`, in three states:
  - active: `border-primary/40 bg-primary/5`, icon circle `bg-primary/15 text-primary` with `animate-pulse`, label "In progress…" `text-xs text-primary font-medium animate-pulse`, mini bar `w-16 h-1.5 bg-muted rounded-full` with fill `animate-bar-sweep`
  - done: `border-border/20 bg-card/30 opacity-60`, circle `bg-green-500/15 text-green-400` with Check, label "Done" `text-xs text-green-400`
  - pending: `border-border/20 bg-card/10 opacity-30`, circle `bg-muted text-muted-foreground`
- Icon circle: `w-9 h-9 rounded-full flex items-center justify-center shrink-0`.

### 7.13 Score ring

```ts
@Component({
  selector: 'app-score-ring',
  standalone: true,
  template: `
    <div class="flex flex-col items-center">
      <div class="relative" [style.width.px]="box()" [style.height.px]="box()">
        <svg [attr.width]="box()" [attr.height]="box()" class="-rotate-90">
          <circle [attr.cx]="c()" [attr.cy]="c()" [attr.r]="r()" fill="none" stroke="hsl(var(--border))" [attr.stroke-width]="stroke()" />
          <circle [attr.cx]="c()" [attr.cy]="c()" [attr.r]="r()" fill="none" [attr.stroke]="color().stroke" [attr.stroke-width]="stroke()"
                  stroke-linecap="round" [attr.stroke-dasharray]="circ()" [attr.stroke-dashoffset]="offset()"
                  style="transition: stroke-dashoffset 1.2s ease-out" />
        </svg>
        <div class="absolute inset-0 flex items-center justify-center">
          <span class="font-display font-bold" [class]="(size() === 'lg' ? 'text-3xl ' : 'text-lg ') + color().text">{{ score() }}</span>
        </div>
      </div>
      @if (label()) { <span class="text-xs text-muted-foreground mt-2">{{ label() }}</span> }
    </div>`,
})
export class ScoreRingComponent {
  readonly score = input.required<number>();
  readonly label = input<string>();
  readonly size = input<'lg' | 'sm'>('lg');
  protected readonly r = computed(() => (this.size() === 'lg' ? 54 : 36));
  protected readonly stroke = computed(() => (this.size() === 'lg' ? 6 : 4));
  protected readonly c = computed(() => this.r() + this.stroke());
  protected readonly box = computed(() => this.c() * 2);
  protected readonly circ = computed(() => 2 * Math.PI * this.r());
  private readonly shown = signal(0);
  protected readonly offset = computed(() => this.circ() - (this.shown() / 100) * this.circ());
  protected readonly color = computed(() => {
    const s = this.score();
    if (s >= 80) return { text: 'text-green-400', stroke: '#4ade80' };
    if (s >= 60) return { text: 'text-yellow-400', stroke: '#facc15' };
    if (s >= 40) return { text: 'text-orange-400', stroke: '#fb923c' };
    return { text: 'text-red-400', stroke: '#f87171' };
  });
  constructor() { afterNextRender(() => requestAnimationFrame(() => this.shown.set(this.score()))); }
}
```

(If `score` changes after first render, add an `effect(() => this.shown.set(this.score()))` instead.)

### 7.14 Selectable tile grid (style selector)

`grid grid-cols-3 gap-3`; tile `relative p-4 rounded-xl border transition-all duration-200 text-center`:
- selected: `border-primary bg-primary/10 ring-2 ring-primary/30`, plus a corner check `absolute top-2 right-2 w-5 h-5 rounded-full bg-primary` with Check `w-3 h-3 text-white`
- idle: `border-border/50 bg-card/50 hover:border-primary/30 hover:bg-card`
- icon `w-6 h-6 mx-auto mb-2` in its accent, label `text-xs font-medium`.

### 7.15 Segmented toggle (device switcher in preview frame)

Wrapper `flex gap-1 p-2 items-center`, buttons `p-2 rounded-md`, active `bg-primary/20 text-primary`, idle `text-muted-foreground hover:text-foreground hover:bg-muted`. Tabs above the frame: `px-5 py-3 text-sm font-medium border-b-2 transition-colors`. Frame wrapper: `w-full rounded-xl overflow-hidden border border-border/40 bg-card`. Mobile stage: `bg-gray-200 py-6`; desktop stage: `bg-gray-50`.

### 7.16 List row (dashboard jobs)

`flex items-center justify-between p-3 rounded-xl hover:bg-muted/30 transition-colors`. Title `font-medium text-sm truncate`, meta row `flex items-center gap-2 mt-1` (status pill + `text-xs text-muted-foreground`), action `uiButton size="sm" variant="outline" class="gap-1 text-xs border-primary/30 text-primary hover:bg-primary/10"`. Empty state: `text-center py-8`, `text-sm text-muted-foreground mb-4`, then a small primary button.

### 7.17 Chat widget

- Container: `fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3`
- FAB: `w-14 h-14 rounded-full bg-gradient-to-r from-primary to-purple-500 text-white shadow-lg hover:shadow-xl transition-[box-shadow,transform] hover:scale-110 active:scale-95 flex items-center justify-center`, toggling MessageCircle / X
- Panel: `w-[360px] h-[520px] rounded-2xl border border-border bg-card shadow-2xl flex flex-col overflow-hidden animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-4`
- Avatar image: `/assets/media/chat-avatar-reed.png` (1.2 MB PNG; consider resizing it to 80×80 WebP)
- Header: `bg-gradient-to-r from-primary to-purple-500 text-white p-4 flex items-center justify-between`, avatar `w-10 h-10 rounded-full object-cover border-2 border-white/30`, name `font-semibold leading-tight`, status `text-xs text-white/70` ("AI Assistant • Online"), close button `hover:bg-white/20 p-1 rounded`
- Messages: `flex-1 overflow-y-auto p-4 space-y-4`. Bubble `max-w-[230px] px-4 py-2.5 rounded-2xl text-sm leading-relaxed`; user `bg-primary text-white rounded-br-none` (right-aligned), bot `bg-muted text-foreground rounded-bl-none` with a `w-7 h-7` avatar
- Composer: `border-t border-border p-4 flex gap-2`, `uiInput class="flex-1"` + `uiButton size="icon"` (Send)

On phones, cap the panel width: add `max-w-[calc(100vw-3rem)]`.

### 7.18 Floating websites background

A fixed, non-interactive layer of 20 tiny "website screenshot" cards drifting across the screen at 12% opacity. It's the most distinctive part of the look.

```ts
@Component({
  selector: 'app-floating-websites-bg',
  standalone: true,
  imports: [NgTemplateOutlet],
  styles: [`
    @keyframes drift-left  { from { transform: translateX(120vw) rotate(var(--rot)); } to { transform: translateX(-300px) rotate(var(--rot)); } }
    @keyframes drift-right { from { transform: translateX(-300px) rotate(var(--rot)); } to { transform: translateX(120vw) rotate(var(--rot)); } }
    @keyframes drift-up    { from { transform: translateY(110vh) rotate(var(--rot)); } to { transform: translateY(-150px) rotate(var(--rot)); } }
    @keyframes drift-down  { from { transform: translateY(-150px) rotate(var(--rot)); } to { transform: translateY(110vh) rotate(var(--rot)); } }
    .card { position:absolute; width:160px; height:110px; border-radius:10px; overflow:hidden; opacity:.12;
            box-shadow:0 6px 28px rgba(0,0,0,.45); border:1px solid rgba(255,255,255,.07);
            animation: var(--anim) var(--dur) linear var(--delay) infinite; }
    @media (prefers-reduced-motion: reduce) { :host { display:none; } }
  `],
  template: `
    <div style="position:fixed;inset:0;overflow:hidden;z-index:0;pointer-events:none" aria-hidden="true">
      @for (c of cards; track c.key) {
        <div class="card"
             [style.top]="c.horizontal ? c.cross + '%' : '0'" [style.left]="c.horizontal ? '0' : c.cross + '%'"
             [style.--rot]="c.rot + 'deg'" [style.--anim]="'drift-' + c.dir"
             [style.--dur]="c.dur + 's'" [style.--delay]="c.delay + 's'">
          <ng-container *ngTemplateOutlet="templates[c.tpl]" />
        </div>
      }
    </div>

    <!-- One <ng-template> per mini site. Port the 13 JSX templates from
         src/components/FloatingWebsitesBg.jsx: convert each style={{ a: 1 }} object
         to a style="a:1px" attribute; markup is otherwise identical. -->
    <ng-template #agency> … </ng-template>
    <ng-template #wedding> … </ng-template>
    …
  `,
})
export class FloatingWebsitesBgComponent {
  @ViewChildren(TemplateRef) private tplList!: QueryList<TemplateRef<unknown>>;
  protected templates: TemplateRef<unknown>[] = [];
  protected readonly cards = Array.from({ length: 20 }, (_, i) => {
    const dir = (['left', 'right', 'up', 'down'] as const)[i % 4];
    const dur = 32 + Math.random() * 26;
    return {
      key: i, dir, horizontal: dir === 'left' || dir === 'right', tpl: i % 13,
      rot: Math.random() * 10 - 5, cross: 4 + (i / 20) * 88 + (Math.random() * 5 - 2.5),
      dur, delay: -(Math.random() * dur),
    };
  });
  ngAfterViewInit() { this.templates = this.tplList.toArray(); this.cdr.detectChanges(); }
  private readonly cdr = inject(ChangeDetectorRef);
}
```

This replaces the 20 generated `@keyframes` from the React version with 4 shared ones driven by CSS variables. It looks the same and costs less. Content layers above it need `relative z-10` (already present in the public layout).

---

## 8. Page assembly: Home section order

1. Hero (§7.2)
2. Live counter bar (§7.9)
3. Brand marquee (§7.9)
4. Stats + platform chips (§7.4 stat tile, §7.6 chip): `py-20`, stats grid `grid-cols-2 lg:grid-cols-4 gap-6 mb-20`
5. How It Works: step cards
6. Features ("Everything You Need"): icon cards, 3-up
7. Pricing ("Simple Pricing"): §7.5
8. Why Choose Us: horizontal icon cards, 2-up
9. Video demo · Industry callouts · Comparison table · Press · Use cases · Platform support
10. Testimonials (3-up, `max-w-6xl`)
11. Trust badges
12. Email capture
13. FAQ
14. Final CTA: `py-24 px-4 border-t border-border/20 text-center`, `max-w-2xl`, button `h-14 px-10 text-lg font-bold rounded-xl bg-green-500 hover:bg-green-600 active:bg-green-700 text-white`, smooth-scrolls to `#hero`
15. Contact section (`id="contact"`), §7.10, with a soft glow `absolute bottom-0 right-0 w-[500px] h-[500px] bg-primary/5 rounded-full blur-[120px]`

The sections in item 9 follow the same recipes: section wrapper + section header + one of the card types.

---

## 9. Gotchas when porting

1. **Tailwind classes with `/`, `[`, or `:` can't be used in `[class.x]` bindings.** `[class.bg-primary/10]="…"` and `[class.grid-rows-[1fr]]="…"` won't compile. Use `[class]="cond ? '…' : '…'"` next to the static `class` attribute (Angular merges the two).
2. **No dynamic class construction.** `'text-' + c + '-400'` produces no CSS. Use the `ACCENTS` map.
3. **Content globs** must include `.ts`, because class strings live in component constants and inline templates.
4. **Icons:** `lucide-angular` renders `<lucide-icon>` wrapping an `<svg>`. Size it with `class="w-4 h-4"` on the host (lucide's own CSS makes the SVG fill it), or with `[size]="16"`. The button's `[&_svg]:size-4` rule still applies to the inner SVG, so to get a bigger icon inside a button, override it on the button (`[&_svg]:size-5`).
5. **Opacity steps:** Tailwind 3's default opacity scale has no `/8`; the source's `bg-purple-500/8` generates nothing. Use `/[0.08]`, or `/5` and `/10`.
6. **`tailwind-merge` v2.x only** with Tailwind 3 (see §1.1).
7. **Avoid nested interactive elements.** Put `uiButton` on the `<a routerLink>` itself instead of wrapping a `<button>` in a link.
8. **Z-index stack:** floating background `z-0` → content `z-10` → dashboard header `z-40` → nav, drawer, modals, and chat `z-50`.
9. **SSR:** guard `localStorage`, `IntersectionObserver`, and `Math.random()` (the background) with `isPlatformBrowser` / `afterNextRender`, or the server and client renders won't match.

## 10. Inconsistencies in the source (decide before porting)

- **Brand name:** the navbar uses the **ReeDo** logo, the footer says "ReeDo" next to a Sparkles mark, and the dashboard sidebar and `<title>` say **ElevateWeb**. Pick one name and one mark.
- **Navbar link color** is hard-coded `text-white` rather than `text-foreground`. On this dark theme you can't see a difference, but it would break a light theme.
- **Dark-only:** `:root` and `.dark` are identical. If you ever need light mode, define real light values in `:root` and keep the current ones under `.dark`.
- **Toasts** use the light sonner theme on a dark UI (§6.2).
- **Two hero designs exist** (`pages/Home.jsx` is the live one; `landing/HeroSection.jsx` is the older gradient-button version). This blueprint treats Home.jsx as canonical.

## 11. Parity checklist

- [ ] Inter body and Poppins headings load (check that weight 900 renders on H2s)
- [ ] Page background is `#0d0e12`; cards look translucent over the drifting background
- [ ] The hero form pulses green, and the CTA turns green once the input has text
- [ ] Section borders are faint (`/20`), card borders `/40`, chrome `/50`
- [ ] Feature grid accents in order: cyan, purple, blue, orange, green, pink
- [ ] The "Recommended" pricing card has the orange pill and the orange button
- [ ] Nav collapses below `md`; the sidebar becomes a drawer below `lg`
- [ ] Sections fade up on scroll with stagger; all motion stops under `prefers-reduced-motion`
- [ ] Marquee loops without a seam, with fade edges on both sides
- [ ] Chat FAB stays in the bottom-right on every page, above everything else
- [ ] Focus rings are visible (1px violet `ring-ring`) on buttons and inputs
- [ ] No `images.unsplash.com`, `media.base44.com`, `wikimedia` or other remote asset URLs left in templates; everything loads from `/assets/…` (§12)

---

## 12. Assets: source location → destination

All assets live in **`ui-assets/`** at the root of this repo (`I:\Download-PC\tremendous-elevate-web-flow\ui-assets\`, about 6.9 MB). In the source app they were hot-linked from remote URLs and nothing was stored locally, so these are downloaded copies. The original URLs are kept in `manifest.json` in case you need to download them again.

### 12.1 How to copy (agent instructions)

1. Read `ui-assets/manifest.json`. Each entry has `file` (path in this repo), `copyTo` (path in the Angular project), `servedAt` (URL to use in templates), `status`, `sourceUrl` and `usedBy`.
2. Copy every entry with `"status": "ok"` from `file` to `copyTo`. Skip entries with `"status": "missing-404-at-source"`.
3. In templates, reference assets by `servedAt` (e.g. `src="/assets/images/testimonials/sarah-m.jpg"`), never by `sourceUrl`.
4. **Angular 18+** serves the `public/` folder at `/`, so `public/assets/…` becomes `/assets/…`. **Angular 17 and older:** copy into `src/assets/…` instead; the URLs stay the same.
5. Don't copy `ui-assets/reference/`. It holds source files for the agent to read, not to ship.

One-shot copy (bash, run from the Angular project root; `SRC` is this repo):

```bash
SRC="/i/Download-PC/tremendous-elevate-web-flow/ui-assets"
mkdir -p public/assets
cp -r "$SRC/images" "$SRC/media" "$SRC/logos" "$SRC/brand" public/assets/
cp "$SRC/brand/reedo-mark.svg" public/favicon.svg
```

PowerShell equivalent:

```powershell
$SRC = "I:\Download-PC\tremendous-elevate-web-flow\ui-assets"
New-Item -ItemType Directory -Force public\assets | Out-Null
"images","media","logos","brand" | ForEach-Object { Copy-Item -Recurse -Force "$SRC\$_" public\assets\ }
Copy-Item "$SRC\brand\reedo-mark.svg" public\favicon.svg
```

Then in `index.html`: `<link rel="icon" type="image/svg+xml" href="/favicon.svg" />`. The source app uses the Base44 platform logo as its favicon; this replaces it with the ReeDo mark.

### 12.2 Inventory

| Folder in `ui-assets/` | Files | Used by (source) | Blueprint section |
|---|---|---|---|
| `brand/` | `reedo-logo.svg`, `reedo-mark.svg`, `google-icon.svg` | `ReeDoLogo.jsx`, favicon, `GoogleIcon.jsx` | §7.1, §6.6 |
| `media/` | `chat-avatar-reed.png`, `video-demo.mp4`, `video-demo-poster.jpg`, `team-bob-plumber.png` | `ChatBot.jsx`, `home/VideoDemo.jsx`, `landing/BeforeAfterDemo.jsx` | §7.17, §8 |
| `images/testimonials/` | `sarah-m`, `james-l`, `maria-c`, `david-k`, `amanda-r`, `michael-t`, `rachel-p`, `tom-w`, `priya-s` (.jpg, 150×150) | `home/Testimonials.jsx`, `landing/TestimonialsSection.jsx`, `pages/Scan.jsx` | §7.4 |
| `images/floating-bg/` | `mixed-corporate-woman.jpg`, `bexar-man.jpg`, `business-solutions-woman.jpg` | `FloatingWebsitesBg.jsx` (mini sites 11, 12, 13) | §7.18 |
| `images/before-after/` | `ecommerce-before`, `corporate-before`, `saas-after` | `home/BeforeAfter.jsx` | §8 |
| `images/results-showcase/` | law / restaurant / medical × before / after | `home/ResultsShowcase.jsx` | §8 |
| `images/template-showcase/` | `modern-ecommerce`, `corporate-solutions`, `creative-agency`, `saas-tech` | `home/TemplateShowcase.jsx` | §8 |
| `images/` | `preview-default-hero.jpg` | `preview/InteractiveWebsitePreview.jsx` (fallback hero) | — |
| `logos/trusted/` | `google.png`, `amazon.svg`, `microsoft.svg`, `figma.svg`, `adobe.ico`, `slack.ico` | `layout/Footer.jsx` "Trusted by" strip | §6.4 |
| `reference/` (read-only) | `index.css`, `tailwind.config.js`, `FloatingWebsitesBg.jsx`, `ReeDoLogo.jsx` | source of truth for tokens and the 13 mini-site templates | §1, §7.1, §7.18 |

### 12.3 Notes

- **4 images are already broken in the live app:** the Unsplash photos for `before-after/ecommerce-after`, `before-after/corporate-after`, `before-after/saas-before` and the Scan page's Amanda R. avatar now return 404. Replace them with your own images, and reuse `testimonials/amanda-r.jpg` for the avatar. `BeforeAfter` and `ResultsShowcase` are imported in `Home.jsx` but not rendered at the moment.
- **Not files:** icons come from `lucide-angular`, and fonts come from Google Fonts (§1.3). To self-host the fonts instead, download Inter (400–800) and Poppins (500–900) as `.woff2` files into `public/assets/fonts/` and swap the `<link>` for `@font-face` rules.
- **Large files:** `chat-avatar-reed.png` (1.2 MB) and `team-bob-plumber.png` (1.4 MB) are oversized for how they're displayed. Convert them to WebP at display size before shipping.
- **Licensing:** the Unsplash photos are free to use under the Unsplash License. The trusted-by logos (Google, Amazon, Microsoft, Figma, Adobe, Slack) are third-party trademarks, so check you're entitled to show them before shipping.
- **Brand logo:** `reedo-logo.svg` uses Georgia via a `<text>` element, so it renders slightly differently on systems without that font. The `LogoComponent` (§7.1) is the exact version; use the SVG only where a component can't go (emails, OG images, favicon).
