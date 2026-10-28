import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideAngularModule, LucideIconData } from 'lucide-angular';

import { LogoComponent } from '../shared/components/logo.component';

/** Blueprint §6.6 auth layout: icon tile, title, subtitle, card body, and a
 * footer slot under the card. */
@Component({
  selector: 'app-auth-layout',
  standalone: true,
  imports: [LucideAngularModule, RouterLink, LogoComponent],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div class="w-full max-w-md">
        <div class="flex justify-center mb-8">
          <a routerLink="/" aria-label="ReDoWebs home"><app-logo size="md" /></a>
        </div>
        <div class="text-center mb-10">
          <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary mb-4">
            <lucide-icon [img]="icon()" class="w-7 h-7 text-primary-foreground" aria-hidden="true" />
          </div>
          <h1 class="text-3xl font-bold tracking-tight text-foreground">{{ title() }}</h1>
          @if (subtitle()) {
            <p class="text-muted-foreground mt-2">{{ subtitle() }}</p>
          }
        </div>
        <div class="bg-card rounded-2xl shadow-sm border border-border p-8"><ng-content /></div>
        <div class="text-center text-sm text-muted-foreground mt-6"><ng-content select="[authFooter]" /></div>
      </div>
    </div>
  `,
})
export class AuthLayoutComponent {
  readonly icon = input.required<LucideIconData>();
  readonly title = input.required<string>();
  readonly subtitle = input<string>();
}
