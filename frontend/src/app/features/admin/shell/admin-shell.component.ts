import { Component } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../../../core/auth.service';

/** Layout shell for the whole /admin section: top nav + <router-outlet>,
 * matching the design system's flat `.nav` bar rather than a sidebar.
 *
 * Nav only lists pages that actually exist yet (Overview) -- more entries
 * get added here as Usage/Revenue/Users/Projects/Tiers are built in later
 * phases, rather than linking to routes that don't exist. */
@Component({
  selector: 'app-admin-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <nav class="nav">
      <a class="nav-brand" routerLink="/admin"
        >ReDoWebs <span class="label" style="display: inline; color: var(--color-accent-700)">ADMIN</span></a
      >
      <a routerLink="/admin/overview" ariaCurrentWhenActive="page" routerLinkActive>Overview</a>
      <a routerLink="/app">← Back to app</a>
      <span class="label">{{ auth.currentUser()?.email }}</span>
      <button type="button" class="btn btn-ghost" (click)="signOut()">Sign out</button>
    </nav>

    <div class="wrap band">
      <router-outlet />
    </div>
  `,
})
export class AdminShellComponent {
  constructor(
    readonly auth: AuthService,
    private readonly router: Router
  ) {}

  signOut(): void {
    this.auth.logout();
    this.router.navigate(['/']);
  }
}
