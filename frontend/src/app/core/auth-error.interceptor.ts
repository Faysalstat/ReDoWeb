import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { AuthService } from './auth.service';

/** On any 401, forces a logout -- except calls to /auth/* endpoints
 * themselves, where a 401 legitimately means "sign-in failed", not
 * "session expired". */
export const authErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  return next(req).pipe(
    catchError((error) => {
      if (error?.status === 401 && !req.url.includes('/api/v1/auth/')) {
        auth.logout();
      }
      return throwError(() => error);
    })
  );
};
