import { Routes } from '@angular/router';

import { adminGuard, authGuard, redirectIfAuthenticatedGuard } from './core/auth.guard';
import { AuthCallbackComponent } from './pages/auth-callback/auth-callback.component';
import { HomeComponent } from './pages/home/home.component';

/** Same URLs as the classic frontend, so the backend's OAuth redirect
 * (/auth/callback) and checkout/return URLs keep working unchanged. */

export const routes: Routes = [
  { path: '', component: HomeComponent },
  {
    path: 'login',
    canActivate: [redirectIfAuthenticatedGuard],
    loadComponent: () => import('./pages/login/login.component').then((m) => m.LoginComponent),
  },
  { path: 'auth/callback', component: AuthCallbackComponent },
  {
    path: 'projects/:id',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/project/project.component').then((m) => m.ProjectComponent),
  },
  {
    path: 'history',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/history/history.component').then((m) => m.HistoryComponent),
  },
  {
    path: 'pricing',
    loadComponent: () => import('./pages/pricing/pricing.component').then((m) => m.PricingComponent),
  },
  {
    path: 'checkout',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/checkout/checkout.component').then((m) => m.CheckoutComponent),
  },
  {
    path: 'settings/billing',
    canActivate: [authGuard],
    loadComponent: () => import('./pages/billing/billing.component').then((m) => m.BillingComponent),
  },
  {
    path: 'admin',
    canActivate: [adminGuard],
    loadChildren: () => import('./admin/admin.routes').then((m) => m.ADMIN_ROUTES),
  },
  { path: '**', redirectTo: '' },
];
