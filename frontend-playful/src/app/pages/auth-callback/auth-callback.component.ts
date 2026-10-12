import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth.service';

/** Landing spot for the backend's OAuth2 redirect: reads ?token= (success)
 * or ?error= (failure) from the URL, completes the session, and moves on.
 * Failures stay on screen (with Try again) rather than auto-redirecting, so
 * the reason is actually readable. */
@Component({
  selector: 'pg-auth-callback',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="cb">
      <div class="pg-card cb__card">
        @if (error()) {
          <span class="pg-chip pg-chip--danger">Sign-in failed</span>
          <p role="alert">{{ error() }}</p>
          <div class="cb__actions">
            <a class="pg-btn pg-btn--sm" routerLink="/login">Try again</a>
            <a class="pg-btn pg-btn--sm pg-btn--secondary" routerLink="/">Home</a>
          </div>
        } @else {
          <span class="cb__dots" aria-hidden="true"><i></i><i></i><i></i></span>
          <p>Signing you in…</p>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .cb {
        display: grid;
        place-items: center;
        min-height: 60vh;
        padding: 48px 16px;
      }
      .cb__card {
        display: grid;
        justify-items: center;
        gap: 14px;
        text-align: center;
        font-weight: 600;
      }
      .cb__actions {
        display: flex;
        gap: 10px;
      }
      .cb__dots {
        display: flex;
        gap: 8px;
      }
      .cb__dots i {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        border: var(--pg-bw) solid var(--pg-fg);
        background: var(--pg-accent);
        animation: pg-pop-in 700ms var(--pg-bounce) infinite alternate;
      }
      .cb__dots i:nth-child(2) {
        background: var(--pg-pink);
        animation-delay: 150ms;
      }
      .cb__dots i:nth-child(3) {
        background: var(--pg-amber);
        animation-delay: 300ms;
      }
    `,
  ],
})
export class AuthCallbackComponent implements OnInit {
  readonly error = signal('');
  private readonly route = inject(ActivatedRoute);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    const token = params.get('token');
    const oauthError = params.get('error');

    if (oauthError) {
      console.warn('[auth] backend returned a sign-in error:', oauthError);
      this.error.set(oauthError);
      return;
    }

    if (!token) {
      console.warn('[auth] /auth/callback reached without ?token= or ?error=', location.href);
      this.error.set('No sign-in token was received. Please try again.');
      return;
    }

    this.auth.completeLogin(token).subscribe({
      next: () => this.router.navigate(['/']),
      error: (err) => {
        console.warn('[auth] token was issued but GET /auth/me rejected it:', err?.status, err?.error);
        this.auth.logout();
        this.error.set(`Signed in with Google, but the server rejected the session (HTTP ${err?.status ?? '?'}). Please try again.`);
      },
    });
  }
}
