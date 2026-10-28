import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
  provideZoneChangeDetection,
} from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter, withInMemoryScrolling } from '@angular/router';

import { routes } from './app.routes';
import { authErrorInterceptor } from './core/auth-error.interceptor';
import { authInterceptor } from './core/auth.interceptor';
import { TierLabelService } from './core/tier-label.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    // Anchors like /#hero and /#how-it-works, and scroll-to-top on navigation.
    provideRouter(routes, withInMemoryScrolling({ anchorScrolling: 'enabled', scrollPositionRestoration: 'top' })),
    provideHttpClient(withInterceptors([authInterceptor, authErrorInterceptor])),
    // Fire-and-forget: tier labels load in the background, never blocking startup.
    provideAppInitializer(() => inject(TierLabelService).load()),
  ],
};
