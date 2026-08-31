import { Routes } from '@angular/router';

import { adminGuard, authGuard, redirectIfAuthenticatedGuard } from './core/auth.guard';
import { AuthCallbackComponent } from './features/auth-callback/auth-callback.component';
import { GenerationProgressComponent } from './features/generation/generation-progress.component';
import { HistoryComponent } from './features/history/history.component';
import { HomeComponent } from './features/home/home.component';
import { WelcomeComponent } from './features/welcome/welcome.component';

export const routes: Routes = [
  { path: '', component: WelcomeComponent, canActivate: [redirectIfAuthenticatedGuard] },
  { path: 'auth/callback', component: AuthCallbackComponent },
  { path: 'app', component: HomeComponent, canActivate: [authGuard] },
  { path: 'projects/:id', component: GenerationProgressComponent, canActivate: [authGuard] },
  { path: 'history', component: HistoryComponent, canActivate: [authGuard] },
  {
    path: 'admin',
    canActivate: [adminGuard],
    loadChildren: () => import('./features/admin/admin.routes').then((m) => m.ADMIN_ROUTES),
  },
  // Unwired preview-only routes -- no backend behind these yet (no tiers
  // table pricing, no Stripe, no billing). Ported from the angular-app
  // design so the UI exists ready for later wiring; see docs/PROGRESS.md.
  {
    path: 'pricing',
    loadComponent: () => import('./features/pricing/pricing.component').then((m) => m.PricingComponent),
  },
  {
    path: 'checkout',
    loadComponent: () => import('./features/checkout/checkout.component').then((m) => m.CheckoutComponent),
  },
  {
    path: 'settings/billing',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/billing-settings/billing-settings.component').then((m) => m.BillingSettingsComponent),
  },
  { path: '**', redirectTo: '' },
];
