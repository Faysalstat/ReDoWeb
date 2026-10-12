# frontend-playful

An experimental frontend for ReDoWebs in the **Playful Geometric** design system: cream paper background, violet/pink/amber/mint confetti colours, Outfit + Plus Jakarta Sans, 2px borders, hard offset shadows and bouncy motion. The design source is [`backend/prompts/service_playful_prompt.txt`](../backend/prompts/service_playful_prompt.txt).

It's a standalone Angular 20 project. It talks to the same FastAPI backend as [`frontend/`](../frontend) but shares no code with it.

## Run

```bash
cd frontend-playful
npm install
npm start        # http://localhost:4200
```

It uses the same port and the same URLs as `frontend/`, so the backend's CORS setting and the Google sign-in redirect (`/auth/callback`) work unchanged. **Run one frontend at a time.** Stop `frontend/`'s `ng serve` before starting this one, and the reverse.

`npm run build` writes to `dist/frontend-playful/browser/`.

## Layout

| Path | What it holds |
|---|---|
| `src/styles.css` | Design tokens and component classes (`.pg-btn`, `.pg-card`, `.pg-input`, `.pg-chip`, `.pg-table`, `.pg-meter`, decorations, motion). Everything is scoped under the `.pg` root in `app.ts`. Retune the look here. |
| `src/admin-theme.css` | The admin pages' theme ("quiet playful"). Scoped under `.pg-admin`, it re-maps the classic `--color-*` token names onto the playful palette and restyles the classic class names (`.btn`, `.card`, `.table`, `.cells`, …) that the copied admin markup uses. |
| `src/app/core/` | API, auth, guards, interceptors, wallet, PayPal loader and models, **copied** from `frontend/src/app/core/` on 2026-10-12. If a backend endpoint changes, update both copies. The project page (`pages/project/`) and checkout (`pages/checkout/`) also carry copied logic from their classic counterparts. |
| `src/app/layout/` | Header, footer, logo |
| `src/app/ui/` | Icons (inlined Lucide paths, drawn with 2.5px strokes via CSS) and the credit-pack grid |
| `src/app/pages/` | One folder per user-facing page (home, login, auth-callback, project, history, pricing, checkout, billing) |
| `src/app/admin/` | The admin panel, **copied** from `frontend/src/app/features/admin/` on 2026-10-12. Logic and markup are unchanged; only the shell (`admin/shell/`) is new. `admin/ui/` holds copies of the classic badge, button, card and spinner components it uses. |

## Status

Last synced with the classic frontend on 2026-10-12, after the `payment-imp` merge. That merge added preview expiry (History chip + dialog and the project page's expired states), the memoized preview URL that stops the iframe reloading, and the admin soft delete.


Every route from `frontend/` is built:

| Route | Page |
|---|---|
| `/` | Home and URL submit |
| `/login`, `/auth/callback` | Google sign-in |
| `/projects/:id` | Progress, cost approval, error, and ready states. Covers preview, buy, and the post-purchase actions with live SEO progress. |
| `/history` | Project list |
| `/pricing` | Credit packs and FAQ |
| `/checkout` | PayPal (or test-mode) payment |
| `/settings/billing` | Wallet and purchase history |
| `/admin/*` | All 10 admin pages |
