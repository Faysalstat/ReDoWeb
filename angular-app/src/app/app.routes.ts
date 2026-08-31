import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./pages/landing/landing.component').then(m => m.LandingComponent), title: 'REFIT — your site, rebuilt' },
  { path: 'scan/:id', loadComponent: () => import('./pages/scan/scan.component').then(m => m.ScanComponent), title: 'Rebuilding…' },
  { path: 'preview/:id', loadComponent: () => import('./pages/preview/preview.component').then(m => m.PreviewComponent), title: 'Preview' },
  { path: 'pricing', loadComponent: () => import('./pages/pricing/pricing.component').then(m => m.PricingComponent), title: 'Pricing' },
  { path: 'checkout', loadComponent: () => import('./pages/checkout/checkout.component').then(m => m.CheckoutComponent), title: 'Checkout' },
  { path: 'auth', loadComponent: () => import('./pages/auth/auth.component').then(m => m.AuthComponent), title: 'Sign in' },
  { path: 'dashboard', loadComponent: () => import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent), title: 'My sites' },
  { path: 'settings/billing', loadComponent: () => import('./pages/settings/settings.component').then(m => m.SettingsComponent), title: 'Billing' },
  { path: 'admin', loadComponent: () => import('./pages/admin/admin.component').then(m => m.AdminComponent), title: 'Admin' },
  { path: '**', redirectTo: '' },
];
