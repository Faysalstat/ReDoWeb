import { Routes } from '@angular/router';

import { AdminShellComponent } from './shell/admin-shell.component';

export const ADMIN_ROUTES: Routes = [
  {
    path: '',
    component: AdminShellComponent,
    children: [
      { path: '', redirectTo: 'overview', pathMatch: 'full' },
      {
        path: 'overview',
        loadComponent: () =>
          import('./overview/admin-overview.component').then((m) => m.AdminOverviewComponent),
      },
    ],
  },
];
