# client-ng

A third frontend for ReDoWebs, built from [`docs/ANGULAR_UI_BLUEPRINT.md`](../docs/ANGULAR_UI_BLUEPRINT.md). It uses a dark violet Tailwind 3.4 design with shadcn-style primitives, Inter and Poppins type, translucent cards and drifting "mini website" cards in the background.

It's a standalone Angular 20 project with every feature of [`frontend/`](../frontend). It talks to the same FastAPI backend but shares no code with `frontend/`.

## Run

```bash
cd client-ng
npm install
npm start        # http://localhost:4200
```

It uses the same port and URLs as `frontend/` and `frontend-playful/`, so CORS and the Google sign-in redirect (`/auth/callback`) work unchanged. **Run only one of the three at a time.**

**Backend:** `src/app/core/api-config.ts` has `USE_PRODUCTION_API_LOCALLY` (currently `true`, so `npm start` uses the production Railway backend; set it to `false` for a local backend on `:8123`). With production, Google sign-in returns to the production frontend: change the domain in the address bar to `http://localhost:4200` and keep the `/auth/callback?token=…` part.

`npm run build` writes to `dist/client-ng/browser/`.

## What was copied from `frontend/` (2026-10-27)

These files were copied once and are not shared. **If a backend endpoint or the admin panel changes in `frontend/`, copy the change here by hand.**

| Here | Copied from | Changes |
|---|---|---|
| `src/app/core/` | `frontend/src/app/core/` | One import path (`project-status.ts` → `admin/ui/badge`) |
| `src/app/admin/` | `frontend/src/app/features/admin/` | Import paths only. It is wrapped by `admin-classic-root.component.ts` |
| `src/app/admin/ui/{badge,button,card,spinner}` | `frontend/src/app/shared/ui/` | None |
| `src/app/admin/admin-classic.css` | `frontend/src/styles.css` | Generated: every rule scoped under `.classic-admin` |
| Project page, checkout, history, billing, login and callback logic | The matching `frontend/src/app/features/*` components | Templates rewritten; logic unchanged apart from a few toasts |

To regenerate the admin stylesheet after `frontend/src/styles.css` changes:

```bash
node scripts/scope-admin-css.js ../frontend/src/styles.css src/app/admin/admin-classic.css .classic-admin
```

`src/app/admin/admin-preflight-undo.css` puts browser defaults back inside the admin panel, because client-ng's Tailwind reset would otherwise reach it. Tailwind also skips `src/app/admin/**` when scanning for classes (`tailwind.config.js`).

## Layout

| Path | What it holds |
|---|---|
| `tailwind.config.js`, `src/styles.css` | Blueprint §1.2 and §1.4: tokens, keyframes, and the `reveal` and `glow-flash` utilities |
| `src/app/shared/ui/` | Primitives as attribute directives: `uiButton`, `uiInput`, `uiTextarea`, `uiLabel`, `uiCard*` and `uiBadge` |
| `src/app/shared/motion/` | `reveal` directive (fade-up on scroll) and the `app-count-up` counter |
| `src/app/shared/design/` | `ACCENTS` and `STATUS_PILL` class sets, USD formatting, and the last-project helper |
| `src/app/shared/components/` | Logo, brand mark, section header, status pill, FAQ accordion, credit-pack grid, Google icon, floating-websites background |
| `src/app/layouts/` | Public layout (navbar and footer, also used by `/history` and `/settings/billing`), auth layout |
| `src/app/pages/` | One folder per page |
| `public/assets/` | Images, video and logos copied from the blueprint's `ui-assets/` (see its `manifest.json`) |

## Routes

Every route from `frontend/` exists, with the same URLs:

| Route | Page |
|---|---|
| `/` | Home: hero URL form (with the required ToS checkbox) and the blueprint's marketing sections |
| `/login`, `/auth/callback` | Google sign-in (the backend has no email/password sign-in) |
| `/projects/:id` | Progress, cost approval, error/retry, preview (tier tabs, desktop/phone, fullscreen), buy, download, generate all pages, SEO agent with live progress |
| `/history` | History of your projects (public layout; linked from the navbar when signed in), with preview-expired dialog and free re-download links |
| `/settings/billing` | Credits and purchase history (public layout) |
| `/pricing` | Live credit packs and tier costs, plus FAQ |
| `/checkout` | PayPal Smart Buttons, or the test-mode button |
| `/admin/*` | All 10 admin pages, unchanged from `frontend/` |
| `/privacy`, `/terms` | New, static. **Plain-language drafts, not legal review** |
| `/dashboard` | Redirects to `/history` |

## Placeholder content: replace before launch

`src/app/pages/home/home-content.ts` has a `PLACEHOLDER` block with the blueprint's illustrative social proof:

- the live counter numbers, stats, rating and customer count
- the testimonials, with stock photos
- the "as featured in" marquee
- the "trusted by" logo strip in the footer (third-party trademarks)
- the Agency and DIY columns of the comparison table

None of it is real ReDoWebs data. Product facts on the page (pricing, tiers, what a purchase includes) come from the API or describe how the app actually works.

## Differences from the blueprint

- **Brand:** ReDoWebs, not ReeDo or ElevateWeb. The logo keeps the red R and green D.
- **Skipped:** register, forgot and reset password, chat widget, contact form, email capture, the SEO subscription and the About, Blog and Careers pages. None of them have a backend.
- **Navbar** collapses below `lg` instead of `md`, because the signed-in navbar also shows the credit balance and an Admin link.
- **Pricing cards** show the real credit packs instead of hard-coded plans. "Best value" is only shown when one pack is actually cheaper per credit.
- **Dialogs** use the native `<dialog>` element instead of Angular CDK.
- **Toasts** use ngx-sonner's dark theme.
