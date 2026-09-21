import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { IconCheck } from '../../shared/ui/icons/icons';

/** The login page (route: /login). Two columns: sign-in card on the left,
 * marketing pitch on the right -- for a signed-out visitor who clicked
 * "Generate" on the public homepage and got routed here (see home.component.ts). */
@Component({
  selector: 'app-welcome',
  standalone: true,
  imports: [RouterLink, IconCheck],
  templateUrl: './welcome.component.html',
  styleUrl: './welcome.component.css',
})
export class WelcomeComponent {
  readonly pitchPoints = [
    'Your real copy, contact details and images -- kept intact, never invented.',
    'A live preview in your browser before a single credit is spent on a download.',
    'Three tiers of redesign, generated in under a minute.',
  ];

  constructor(private readonly auth: AuthService) {}

  onGoogleLoginClick(): void {
    this.auth.startGoogleLogin();
  }
}
