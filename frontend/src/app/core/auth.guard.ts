import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';

/** Gates the authenticated routes (/app, /history). By the time this runs,
 * the app-init silent refresh (see app.config.ts) has already resolved, so
 * isAuthenticated() reflects the real session state, not a pre-load guess. */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.isAuthenticated() ? true : router.parseUrl('/');
};

/** Keeps an already-signed-in user from seeing the welcome/login screen
 * again -- sends them straight to /app instead. */
export const redirectIfAuthenticatedGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.isAuthenticated() ? router.parseUrl('/app') : true;
};

/** Gates the /admin section. Unauthenticated users go to the welcome page
 * (same as authGuard); a logged-in but non-admin user goes to /app rather
 * than the welcome page, since they do have a valid session -- just not
 * this permission. */
export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isAuthenticated()) {
    return router.parseUrl('/');
  }
  return auth.currentUser()?.is_admin ? true : router.parseUrl('/app');
};
