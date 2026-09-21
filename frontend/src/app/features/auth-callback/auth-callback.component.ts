import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { AuthService } from '../../core/auth.service';

/** Landing spot for the backend's OAuth2 redirect: reads ?token= (success)
 * or ?error= (failure) from the URL, completes the session, and moves on.
 * No guard -- mirrors the reference architecture's no-guard /auth/callback route. */
@Component({
  selector: 'app-auth-callback',
  standalone: true,
  host: { style: 'display: flex; min-height: 100vh; align-items: center; justify-content: center' },
  template: `
    @if (error()) {
      <p style="color: var(--color-danger); font-size: 14px">{{ error() }}</p>
    } @else {
      <p class="text-muted" style="font-size: 14px">Signing you in...</p>
    }
  `,
})
export class AuthCallbackComponent implements OnInit {
  readonly error = signal('');

  constructor(
    private readonly route: ActivatedRoute,
    private readonly auth: AuthService,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    const token = params.get('token');
    const oauthError = params.get('error');

    if (oauthError) {
      this.error.set(oauthError);
      setTimeout(() => this.router.navigate(['/']), 2000);
      return;
    }

    if (!token) {
      this.router.navigate(['/']);
      return;
    }

    this.auth.completeLogin(token).subscribe({
      next: () => this.router.navigate(['/']),
      error: () => {
        this.error.set('Google sign-in failed. Please try again.');
        setTimeout(() => this.router.navigate(['/']), 2000);
      },
    });
  }
}
