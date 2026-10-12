import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../../core/auth.service';

/** Layout for the whole /admin section: a sticky sidebar of pill links plus
 * the page. Sets the `.pg-admin` scope that styles/admin-theme.css hangs
 * off, which re-skins the admin pages' markup in the playful look. */
@Component({
  selector: 'app-admin-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <div class="pg-admin adm">
      <aside class="adm__aside" aria-label="Admin">
        <div class="adm__brand">
          <span class="pg-chip pg-chip--accent">Admin</span>
          <span class="adm__email" [title]="auth.currentUser()?.email ?? ''">{{ auth.currentUser()?.email }}</span>
        </div>
        <nav class="adm__nav">
          @for (link of links; track link.path; let i = $index) {
            <a [routerLink]="link.path" routerLinkActive="is-active" ariaCurrentWhenActive="page" [style.--c]="colors[i % colors.length]">
              <span class="adm__dot" aria-hidden="true"></span>{{ link.label }}
            </a>
          }
        </nav>
        <div class="adm__foot">
          <a routerLink="/" class="adm__back">← Back to app</a>
          <button type="button" class="pg-btn pg-btn--sm pg-btn--secondary" (click)="signOut()">Sign out</button>
        </div>
      </aside>
      <div class="adm__main">
        <router-outlet />
      </div>
    </div>
  `,
  styles: [
    `
      .adm { display: grid; grid-template-columns: 250px minmax(0, 1fr); min-height: calc(100vh - 74px); }
      .adm__aside {
        position: sticky; top: 74px; align-self: start; height: calc(100vh - 74px); overflow-y: auto;
        display: flex; flex-direction: column; gap: 20px; padding: 28px 18px;
        background: var(--pg-card); border-right: var(--pg-bw) solid var(--pg-fg);
        background-image: var(--pg-dot-grid); background-size: 22px 22px;
      }
      .adm__brand { display: grid; gap: 8px; justify-items: start; padding: 0 8px; }
      .adm__email { font-size: var(--pg-text-xs); color: var(--pg-muted-fg); max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .adm__nav { display: grid; gap: 4px; }
      .adm__nav a {
        display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: var(--pg-radius-full);
        border: var(--pg-bw) solid transparent; color: var(--pg-fg); font-weight: 600; font-size: var(--pg-text-sm);
        text-decoration: none; transition: background-color 150ms ease, transform 300ms var(--pg-bounce);
      }
      .adm__nav a:hover { background: var(--pg-muted); }
      .adm__nav a.is-active { background: var(--pg-card); border-color: var(--pg-fg); box-shadow: 3px 3px 0 var(--c); font-weight: 800; transform: translateX(4px); }
      .adm__dot { width: 10px; height: 10px; flex: none; border-radius: 50%; border: var(--pg-bw) solid var(--pg-fg); background: var(--c); }
      .adm__foot { margin-top: auto; display: grid; gap: 12px; justify-items: start; padding: 16px 8px 0; border-top: var(--pg-bw) dashed var(--pg-border); }
      .adm__back { font-size: var(--pg-text-sm); }
      .adm__main { min-width: 0; padding: 36px 40px 72px; }
      @media (max-width: 880px) {
        .adm { grid-template-columns: 1fr; }
        .adm__aside { position: static; height: auto; border-right: 0; border-bottom: var(--pg-bw) solid var(--pg-fg); padding: 16px; }
        .adm__nav { display: flex; overflow-x: auto; scrollbar-width: none; padding-bottom: 4px; }
        .adm__nav a { flex: none; }
        .adm__nav a.is-active { transform: none; }
        .adm__foot { flex-direction: row; display: flex; align-items: center; justify-content: space-between; width: 100%; margin-top: 0; }
        .adm__main { padding: 24px 16px 56px; }
      }
    `,
  ],
})
export class AdminShellComponent {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly colors = ['var(--pg-accent)', 'var(--pg-pink)', 'var(--pg-amber)', 'var(--pg-mint)'];
  readonly links = [
    { path: '/admin/overview', label: 'Overview' },
    { path: '/admin/users', label: 'Users' },
    { path: '/admin/projects', label: 'Projects' },
    { path: '/admin/payments', label: 'Payments' },
    { path: '/admin/earnings', label: 'Earnings' },
    { path: '/admin/tiers-pricing', label: 'Tiers & pricing' },
    { path: '/admin/costs', label: 'Costs' },
    { path: '/admin/model-config', label: 'Model config' },
    { path: '/admin/prompt-templates', label: 'Prompt templates' },
    { path: '/admin/cost-gate', label: 'Cost gate' },
  ];

  signOut(): void {
    this.auth.logout();
    this.router.navigate(['/']);
  }
}
