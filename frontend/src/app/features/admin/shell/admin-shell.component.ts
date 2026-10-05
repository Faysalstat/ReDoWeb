import { Component } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../../../core/auth.service';

/** Layout shell for the whole /admin section: a `.shell`/`.shell__aside`
 * sidebar (the design system's own "used by dashboard, settings and admin"
 * primitive, per styles.css's comment on it) rather than the flat `.nav`
 * top bar this used before the 2026-09-20 admin panel upgrade -- a top bar
 * was fine for one link (Overview) but doesn't scale to seven. */
@Component({
  selector: 'app-admin-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <div class="shell" style="min-height: 100vh">
      <div class="shell__aside" style="position: sticky; top: 0; height: 100vh; overflow-y: auto">
        <a
          class="nav-brand"
          routerLink="/admin"
          style="margin-bottom: var(--space-3); text-decoration: none; color: var(--color-text)"
          >ReDoWebs <span class="label" style="display: inline; color: var(--color-accent-700)">ADMIN</span></a
        >
        <a class="shell-aside-link" routerLink="/admin/overview" ariaCurrentWhenActive="page" routerLinkActive="active"
          >Overview</a
        >
        <a class="shell-aside-link" routerLink="/admin/users" ariaCurrentWhenActive="page" routerLinkActive="active"
          >Users</a
        >
        <a class="shell-aside-link" routerLink="/admin/projects" ariaCurrentWhenActive="page" routerLinkActive="active"
          >Projects</a
        >
        <a class="shell-aside-link" routerLink="/admin/payments" ariaCurrentWhenActive="page" routerLinkActive="active"
          >Payments</a
        >
        <a class="shell-aside-link" routerLink="/admin/earnings" ariaCurrentWhenActive="page" routerLinkActive="active"
          >Earnings</a
        >
        <a class="shell-aside-link" routerLink="/admin/tiers-pricing" ariaCurrentWhenActive="page" routerLinkActive="active"
          >Tiers &amp; pricing</a
        >
        <a class="shell-aside-link" routerLink="/admin/costs" ariaCurrentWhenActive="page" routerLinkActive="active"
          >Costs</a
        >
        <a class="shell-aside-link" routerLink="/admin/model-config" ariaCurrentWhenActive="page" routerLinkActive="active"
          >Model config</a
        >
        <a class="shell-aside-link" routerLink="/admin/prompt-templates" ariaCurrentWhenActive="page" routerLinkActive="active"
          >Prompt templates</a
        >
        <a class="shell-aside-link" routerLink="/admin/cost-gate" ariaCurrentWhenActive="page" routerLinkActive="active"
          >Cost gate</a
        >
        <div style="margin-top: auto; padding-top: var(--space-4); border-top: 1px solid var(--color-divider)">
          <a class="shell-aside-link" routerLink="/" style="padding-inline: 0">← Back to app</a>
          <p class="label" style="margin: var(--space-3) 0 var(--space-1)">{{ auth.currentUser()?.email }}</p>
          <button type="button" class="btn btn-ghost" style="padding-inline: 0" (click)="signOut()">Sign out</button>
        </div>
      </div>
      <div class="shell__main">
        <router-outlet />
      </div>
    </div>
  `,
  styles: [
    `
      .shell-aside-link {
        color: var(--color-text);
        text-decoration: none;
        font-size: 15px;
        padding: 8px 10px;
        border-radius: var(--radius-sm);
      }
      .shell-aside-link:hover {
        color: var(--color-accent);
        background: color-mix(in srgb, var(--color-accent) 8%, transparent);
      }
      .shell-aside-link.active {
        color: var(--color-accent);
        font-weight: 600;
        background: color-mix(in srgb, var(--color-accent) 12%, transparent);
      }
    `,
  ],
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
