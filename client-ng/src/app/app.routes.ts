import { Routes } from '@angular/router';

import { adminGuard, authGuard, redirectIfAuthenticatedGuard } from './core/auth.guard';

// Same URLs as frontend/, so the backend's Google redirect (/auth/callback),
// checkout return URLs and History links all keep working.
export const routes: Routes = [
  {
    path: 'login',
    canActivate: [redirectIfAuthenticatedGuard],
    loadComponent: () => import('./pages/auth/login.page'),
  },
  { path: 'auth/callback', loadComponent: () => import('./pages/auth/auth-callback.page') },
  {
    path: 'admin',
    canActivate: [adminGuard],
    loadChildren: () => import('./admin/admin.routes').then((m) => m.ADMIN_ROUTES),
  },
  { path: 'dashboard', redirectTo: 'history', pathMatch: 'full' },
  {
    path: '',
    loadComponent: () => import('./layouts/public-layout.component'),
    children: [
      // Public: submit() itself sends a signed-out visitor to /login.
      { path: '', pathMatch: 'full', loadComponent: () => import('./pages/home/home.page') },
      { path: 'pricing', loadComponent: () => import('./pages/pricing/pricing.page') },
      { path: 'privacy', loadComponent: () => import('./pages/legal/privacy.page') },
      { path: 'terms', loadComponent: () => import('./pages/legal/terms.page') },
      {
        path: 'projects/:id',
        canActivate: [authGuard],
        loadComponent: () => import('./pages/project/project.page'),
      },
      { path: 'checkout', canActivate: [authGuard], loadComponent: () => import('./pages/checkout/checkout.page') },
      // Signed-in pages share the public navbar and footer, like the project page.
      { path: 'history', canActivate: [authGuard], loadComponent: () => import('./pages/history/history.page') },
      { path: 'settings/billing', canActivate: [authGuard], loadComponent: () => import('./pages/billing/billing.page') },
      { path: '**', loadComponent: () => import('./pages/not-found.page') },
    ],
  },
];
