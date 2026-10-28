import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

import { AuthService } from '../../core/auth.service';

/** Landing spot for the backend's OAuth2 redirect: reads ?token= (success)
 * or ?error= (failure), completes the session, and moves on. Logic copied
 * from frontend/'s AuthCallbackComponent. */
@Component({
  selector: 'app-auth-callback-page',
  standalone: true,
  template: `
    <div class="fixed inset-0 flex flex-col items-center justify-center gap-4 bg-background px-4 text-center">
      @if (error()) {
        <div class="p-3 rounded-lg bg-destructive/10 text-destructive text-sm">{{ error() }}</div>
      } @else {
        <div class="w-8 h-8 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
        <p class="text-sm text-muted-foreground">Signing you in...</p>
      }
    </div>
  `,
})
export default class AuthCallbackPage implements OnInit {
  readonly error = signal('');

  constructor(
    private readonly route: ActivatedRoute,
    private readonly auth: AuthService,
    private readonly router: Router,
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
