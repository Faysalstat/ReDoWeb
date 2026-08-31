import { Component } from '@angular/core';

import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-welcome',
  standalone: true,
  templateUrl: './welcome.component.html',
  styleUrl: './welcome.component.css',
})
export class WelcomeComponent {
  constructor(private readonly auth: AuthService) {}

  onGoogleLoginClick(): void {
    this.auth.startGoogleLogin();
  }
}
