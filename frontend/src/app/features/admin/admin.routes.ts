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
      {
        path: 'users',
        loadComponent: () =>
          import('./users/admin-users-list.component').then((m) => m.AdminUsersListComponent),
      },
      {
        path: 'users/:id',
        loadComponent: () =>
          import('./users/admin-user-detail.component').then((m) => m.AdminUserDetailComponent),
      },
      {
        path: 'projects',
        loadComponent: () =>
          import('./projects/admin-projects-list.component').then((m) => m.AdminProjectsListComponent),
      },
      {
        path: 'projects/:id',
        loadComponent: () =>
          import('./projects/admin-project-detail.component').then((m) => m.AdminProjectDetailComponent),
      },
      {
        path: 'costs',
        loadComponent: () => import('./costs/admin-costs.component').then((m) => m.AdminCostsComponent),
      },
      {
        path: 'model-config',
        loadComponent: () =>
          import('./model-config/admin-model-config.component').then((m) => m.AdminModelConfigComponent),
      },
      {
        path: 'prompt-templates',
        loadComponent: () =>
          import('./prompt-templates/admin-prompt-templates.component').then(
            (m) => m.AdminPromptTemplatesComponent
          ),
      },
      {
        path: 'earnings',
        loadComponent: () =>
          import('./earnings/admin-earnings.component').then((m) => m.AdminEarningsComponent),
      },
    ],
  },
];
