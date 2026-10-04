import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

/** Nav for the public/unauthenticated marketing pages (pricing, checkout).
 * "Sign in" and the primary CTA both point at "/" -- the welcome screen is
 * this app's only sign-in surface (Google OAuth), there's no separate
 * sign-in route. */
@Component({
  selector: 'app-public-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="nav">
      <a class="nav-brand" routerLink="/">ReDoWebs</a>
      <a routerLink="/pricing" ariaCurrentWhenActive="page" routerLinkActive>Pricing</a>
      <a class="btn btn-ghost" routerLink="/">Sign in</a>
      <a class="btn btn-primary" routerLink="/">Get started</a>
    </nav>
  `,
})
export class PublicNavComponent {}
