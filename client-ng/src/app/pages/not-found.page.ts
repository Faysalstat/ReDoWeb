import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ArrowRight, LucideAngularModule } from 'lucide-angular';

import { UiButton } from '../shared/ui/button.directive';

@Component({
  selector: 'app-not-found-page',
  standalone: true,
  imports: [RouterLink, LucideAngularModule, UiButton],
  template: `
    <section class="py-32 px-4 text-center">
      <div class="max-w-md mx-auto">
        <p class="text-7xl font-black font-display bg-gradient-to-r from-purple-400 via-purple-500 to-blue-500 text-transparent bg-clip-text mb-4">404</p>
        <h1 class="text-2xl sm:text-3xl font-bold mb-3">Page not found</h1>
        <p class="text-muted-foreground mb-8">The page you're looking for doesn't exist or has moved.</p>
        <a uiButton routerLink="/" class="h-11 px-6 rounded-xl text-white">
          Back to home <lucide-icon [img]="ArrowRight" class="w-4 h-4" />
        </a>
      </div>
    </section>
  `,
})
export default class NotFoundPage {
  protected readonly ArrowRight = ArrowRight;
}
