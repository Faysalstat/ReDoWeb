# REFIT — Angular front end

Nine screens of an AI website-regeneration SaaS, built on the **Modernist** design system.
All data is mocked in `src/app/core/refit.service.ts` — wire your APIs there and the UI needs no changes.

## Run

```
npm install
npm start
```

## Routes

| Route | Component | Screen |
| --- | --- | --- |
| `/` | `LandingComponent` | Landing + URL capture |
| `/scan/:id` | `ScanComponent` | Generation progress (percentage, phases, findings) |
| `/preview/:id` | `PreviewComponent` | Before/after compare (side by side + wipe) |
| `/pricing` | `PricingComponent` | Plans and comparison table |
| `/checkout` | `CheckoutComponent` | Payment |
| `/auth` | `AuthComponent` | Sign in / create account |
| `/dashboard` | `DashboardComponent` | Customer's sites |
| `/settings/billing` | `SettingsComponent` | Plan, card, invoices |
| `/admin` | `AdminComponent` | Jobs queue, revenue, failures, tickets |

## Styling

- `src/styles/modernist.css` — the design system, copied verbatim. Do not edit; replace it when the system updates.
- `src/styles/_app.scss` — application layer: page shell, grid utilities, display type, responsive rules. Built only from Modernist tokens (`var(--color-*)`, `var(--space-*)`).
- Components carry their own `.scss` only where a layout is unique to that screen.

## Where the APIs go

`RefitService` exposes the shape the UI expects:

- `startScan(url)` → `POST /api/scans`
- `scan(id)` → `GET /api/scans/:id` (poll or SSE for progress + findings)
- `preview(id)` → `GET /api/previews/:id`
- `plans()` → `GET /api/plans`
- `sites()` → `GET /api/sites`
- `invoices()` → `GET /api/billing/invoices`
- `adminOverview()` → `GET /api/admin/overview`

Each method returns an Observable already, so swapping the mock for `HttpClient` is a one-line change per method.
