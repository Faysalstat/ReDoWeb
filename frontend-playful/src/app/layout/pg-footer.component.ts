import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AuthService } from '../core/auth.service';
import { PgLogoComponent } from './pg-logo.component';

@Component({
  selector: 'pg-footer',
  standalone: true,
  imports: [RouterLink, PgLogoComponent],
  template: `
    <footer class="pgf">
      <svg class="pgf__wave" viewBox="0 0 1200 24" preserveAspectRatio="none" aria-hidden="true">
        <path d="M0 12 Q 25 0 50 12 T 100 12 T 150 12 T 200 12 T 250 12 T 300 12 T 350 12 T 400 12 T 450 12 T 500 12 T 550 12 T 600 12 T 650 12 T 700 12 T 750 12 T 800 12 T 850 12 T 900 12 T 950 12 T 1000 12 T 1050 12 T 1100 12 T 1150 12 T 1200 12" fill="none" stroke="#8B5CF6" stroke-width="3" stroke-linecap="round" />
      </svg>
      <div class="pg-wrap pgf__grid">
        <div class="pgf__brand">
          <pg-logo />
          <p class="pg-muted">
            AI redesigns of the site you already have. Your facts kept intact, nothing published without your
            say-so.
          </p>
        </div>
        <nav class="pgf__col" aria-label="Product">
          <p class="pg-label">Product</p>
          <a routerLink="/">Redesign a site</a>
          <a routerLink="/pricing">Pricing</a>
        </nav>
        @if (auth.isAuthenticated()) {
          <nav class="pgf__col" aria-label="Account">
            <p class="pg-label">Account</p>
            <a routerLink="/history">History</a>
            <a routerLink="/settings/billing">Billing</a>
          </nav>
        }
      </div>
      <div class="pg-wrap pgf__bottom">
        <span>© 2026 ReDoWebs</span>
        <span>We only redesign sites you own or are authorized to submit.</span>
      </div>
    </footer>
  `,
  styles: [
    `
      .pgf {
        margin-top: auto;
        padding-bottom: 32px;
        border-top: var(--pg-bw) solid var(--pg-fg);
        background: var(--pg-card);
      }
      .pgf__wave {
        display: block;
        width: 100%;
        height: 24px;
        margin: 18px 0 40px;
      }
      .pgf__grid {
        display: grid;
        grid-template-columns: 2fr 1fr 1fr;
        gap: 40px;
      }
      .pgf__brand {
        display: grid;
        gap: 14px;
        max-width: 360px;
        font-size: var(--pg-text-sm);
      }
      .pgf__col {
        display: grid;
        align-content: start;
        gap: 10px;
      }
      .pgf__col a {
        color: var(--pg-fg);
        font-weight: 600;
        text-decoration: none;
        font-size: var(--pg-text-sm);
      }
      .pgf__col a:hover {
        color: var(--pg-accent);
        text-decoration: underline;
      }
      .pgf__bottom {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        gap: 8px;
        margin-top: 40px;
        padding-top: 20px;
        border-top: var(--pg-bw) dashed var(--pg-border);
        font-size: var(--pg-text-xs);
        color: var(--pg-muted-fg);
      }
      @media (max-width: 640px) {
        .pgf__grid {
          grid-template-columns: 1fr 1fr;
        }
        .pgf__brand {
          grid-column: 1 / -1;
        }
      }
    `,
  ],
})
export class PgFooterComponent {
  readonly auth = inject(AuthService);
}
