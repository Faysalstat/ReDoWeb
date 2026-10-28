import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const accessToken = inject(AuthService).getAccessToken();
  if (!accessToken) {
    return next(req);
  }
  return next(req.clone({ setHeaders: { Authorization: `Bearer ${accessToken}` } }));
};
