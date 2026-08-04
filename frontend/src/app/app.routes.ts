import { Routes } from '@angular/router';

import { authGuard, redirectIfAuthenticatedGuard } from './core/auth.guard';
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
  { path: '**', redirectTo: '' },
];
