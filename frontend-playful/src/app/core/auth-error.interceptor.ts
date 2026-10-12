import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { AuthService } from './auth.service';

/** On any 401, forces a logout -- except calls to /auth/* endpoints
 * themselves, where a 401 legitimately means "sign-in failed", not
 * "session expired" -- and except unauthenticated calls the public homepage
 * makes itself (e.g. wallet lookups guarded by isAuthenticated() shouldn't
 * even fire, but a stray one shouldn't force a redirect on a public page).
 * On a 403 from an /admin/* call, redirect home instead -- a non-admin user
 * still has a valid session, this isn't an auth failure, just a missing
 * permission, so logging them out would be wrong. */
export const authErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return next(req).pipe(
    catchError((error) => {
      if (error?.status === 401 && !req.url.includes('/api/v1/auth/')) {
        auth.logout();
      }
      if (error?.status === 403 && req.url.includes('/api/v1/admin/')) {
        router.navigateByUrl('/');
      }
      return throwError(() => error);
    })
  );
};
