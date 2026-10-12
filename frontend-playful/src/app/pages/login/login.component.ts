import { Component, inject } from '@angular/core';

import { AuthService } from '../../core/auth.service';
import { IconCheck } from '../../ui/icons';

/** /login: Google sign-in on a sticker card, with a confetti field behind. */
@Component({
  selector: 'pg-login',
  standalone: true,
  imports: [IconCheck],
  template: `
    <section class="login">
      <div class="login__confetti" aria-hidden="true">
        <span class="pg-shape pg-float c c--circle"></span>
        <span class="pg-shape pg-float c c--square"></span>
        <svg class="pg-shape pg-float c c--tri" viewBox="0 0 40 36"><path d="M20 2 L38 34 H2 Z" fill="#F472B6" stroke="#1E293B" stroke-width="2.5" stroke-linejoin="round" /></svg>
        <svg class="pg-shape c c--zig pg-shape--hide-sm" viewBox="0 0 80 20"><path d="M2 14 L14 4 L26 14 L38 4 L50 14 L62 4 L74 14" fill="none" stroke="#8B5CF6" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" /></svg>
        <span class="pg-shape c c--ring pg-shape--hide-sm"></span>
      </div>

      <div class="pg-card pg-card--featured login__card pg-pop-in">
        <span class="pg-kicker">Welcome</span>
        <h1 class="login__title">Hello again! 👋</h1>
        <p class="pg-muted">Sign in to redesign your site and keep track of your previews.</p>

        <button type="button" class="pg-btn pg-btn--secondary pg-btn--block login__google" (click)="signIn()">
          <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
            <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
            <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
            <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
            <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
          </svg>
          Continue with Google
        </button>
        <button type="button" class="pg-btn pg-btn--secondary pg-btn--block login__apple" disabled title="Coming soon">
          <svg width="16" height="18" viewBox="0 0 814 1000" aria-hidden="true">
            <path fill="currentColor" d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76.5 0-103.7 40.8-165.9 40.8s-105.6-57-155.5-127C46.7 790.7 0 663 0 541.8c0-194.4 126.4-297.5 250.8-297.5 66.1 0 121.2 43.4 162.7 43.4 39.5 0 101.1-46 176.3-46 28.5 0 130.9 2.6 198.3 99.2zM554.1 159.4c31.9-37.8 54.4-90.3 54.4-142.8 0-7.3-.6-14.7-1.9-20.6-51.9 1.9-113.6 34.5-150.8 77.9-29.2 33.3-56.4 85.8-56.4 139.1 0 8 1.3 16 1.9 18.6 3.2.6 8.4 1.3 13.6 1.3 46.5 0 105-31.2 139.2-73.5z" />
          </svg>
          Continue with Apple <span class="pg-chip login__soon">Soon</span>
        </button>
        <p class="login__note">3 free credits on signup · free preview always.</p>

        <ul class="login__points">
          @for (p of points; track p) {
            <li>
              <span class="pg-icon-badge pg-icon-badge--mint login__tick"><app-icon-check [size]="12" /></span>
              {{ p }}
            </li>
          }
        </ul>
      </div>
    </section>
  `,
  styles: [
    `
      .login {
        position: relative;
        display: grid;
        place-items: center;
        min-height: calc(100vh - 74px);
        padding: 64px 16px;
        overflow: hidden;
      }
      .login__card {
        position: relative;
        z-index: 1;
        width: 100%;
        max-width: 460px;
        display: grid;
        gap: 18px;
        justify-items: start;
      }
      .login__title {
        font-size: var(--pg-text-3xl);
      }
      .login__google {
        margin-top: 6px;
        background: var(--pg-card);
      }
      .login__apple {
        background: var(--pg-muted);
      }
      .login__soon {
        padding: 1px 8px;
        font-size: 0.7rem;
      }
      .login__note {
        justify-self: stretch;
        text-align: center;
        font-size: var(--pg-text-xs);
        font-weight: 700;
        color: var(--pg-muted-fg);
      }
      .login__points {
        list-style: none;
        margin: 6px 0 0;
        padding: 18px 0 0;
        border-top: var(--pg-bw) dashed var(--pg-border);
        display: grid;
        gap: 12px;
        font-size: var(--pg-text-sm);
      }
      .login__points li {
        display: flex;
        gap: 10px;
        align-items: flex-start;
      }
      .login__tick {
        --_size: 22px;
        box-shadow: none;
      }
      .c {
        border: var(--pg-bw) solid var(--pg-fg);
      }
      .c--circle {
        width: 140px;
        height: 140px;
        border-radius: 50%;
        background: var(--pg-amber);
        top: 12%;
        left: 12%;
      }
      .c--square {
        width: 70px;
        height: 70px;
        border-radius: 14px;
        background: var(--pg-mint);
        bottom: 16%;
        right: 16%;
        animation-delay: -3s;
      }
      .c--tri {
        border: 0;
        width: 56px;
        top: 18%;
        right: 22%;
        animation-delay: -1.5s;
      }
      .c--zig {
        border: 0;
        width: 100px;
        bottom: 22%;
        left: 18%;
      }
      .c--ring {
        width: 64px;
        height: 64px;
        border-radius: 50%;
        border: 10px solid var(--pg-pink);
        top: 62%;
        left: 8%;
      }
    `,
  ],
})
export class LoginComponent {
  private readonly auth = inject(AuthService);

  readonly points = [
    'Your real copy, contact details and images, kept intact and never invented.',
    'A live preview in your browser before any credit is spent on a download.',
    'Several tiers of redesign to compare side by side.',
  ];

  signIn(): void {
    this.auth.startGoogleLogin();
  }
}
