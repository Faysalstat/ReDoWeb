import { Component } from '@angular/core';

import { AuthService } from '../../core/auth.service';
import { ParallaxHeroDirective } from '../../shared/directives/parallax-hero.directive';
import { BadgeComponent } from '../../shared/ui/badge/badge.component';
import { CardComponent } from '../../shared/ui/card/card.component';

@Component({
  selector: 'app-welcome',
  standalone: true,
  imports: [ParallaxHeroDirective, BadgeComponent, CardComponent],
  templateUrl: './welcome.component.html',
})
export class WelcomeComponent {
  constructor(private readonly auth: AuthService) {}

  onGoogleLoginClick(): void {
    this.auth.startGoogleLogin();
  }
}
