import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Check, LogIn, LucideAngularModule } from 'lucide-angular';

import { AuthService } from '../../core/auth.service';
import { AuthLayoutComponent } from '../../layouts/auth-layout.component';
import { GoogleIconComponent } from '../../shared/components/google-icon.component';
import { UiButton } from '../../shared/ui/button.directive';

/** /login: Google sign-in only (the backend has no email/password auth).
 * Same behavior as frontend/'s WelcomeComponent. */
@Component({
  selector: 'app-login-page',
  standalone: true,
  imports: [RouterLink, LucideAngularModule, AuthLayoutComponent, GoogleIconComponent, UiButton],
  template: `
    <app-auth-layout [icon]="icons.LogIn" title="Welcome back" subtitle="Sign in to preview a modern redesign of your site">
      <button uiButton variant="outline" type="button" class="w-full h-12 text-sm font-medium mb-6" (click)="google()">
        <app-google-icon class="w-5 h-5" /> Continue with Google
      </button>

      <ul class="space-y-3">
        @for (point of pitchPoints; track point) {
          <li class="flex items-start gap-3 text-sm text-muted-foreground">
            <lucide-icon [img]="icons.Check" class="w-4 h-4 mt-0.5 text-green-400" />
            <span>{{ point }}</span>
          </li>
        }
      </ul>

      <p class="mt-6 pt-6 border-t border-border text-xs text-muted-foreground text-center">
        3 free credits on signup · free preview always.
      </p>

      <span authFooter>
        By continuing you agree to the <a routerLink="/terms" class="text-primary font-medium hover:underline">Terms</a> and
        <a routerLink="/privacy" class="text-primary font-medium hover:underline">Privacy Policy</a>.
      </span>
    </app-auth-layout>
  `,
})
export default class LoginPage {
  protected readonly icons = { Check, LogIn };
  readonly pitchPoints = [
    'Your real copy, contact details and images, kept intact and never invented.',
    'A live preview in your browser before a single credit is spent on a download.',
    'Several design tiers to choose from, each in its own style.',
  ];

  constructor(private readonly auth: AuthService) {}

  google(): void {
    this.auth.startGoogleLogin();
  }
}
