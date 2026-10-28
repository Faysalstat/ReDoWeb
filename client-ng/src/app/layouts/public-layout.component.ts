import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { FloatingWebsitesBgComponent } from '../shared/components/floating-websites-bg/floating-websites-bg.component';
import { FooterComponent } from './footer.component';
import { NavbarComponent } from './navbar.component';

@Component({
  selector: 'app-public-layout',
  standalone: true,
  imports: [RouterOutlet, NavbarComponent, FooterComponent, FloatingWebsitesBgComponent],
  template: `
    <app-floating-websites-bg />
    <div class="min-h-screen flex flex-col relative">
      <app-navbar />
      <main class="flex-1 pt-16 relative z-10"><router-outlet /></main>
      <app-footer class="relative z-10" />
    </div>
  `,
})
export default class PublicLayoutComponent {}
