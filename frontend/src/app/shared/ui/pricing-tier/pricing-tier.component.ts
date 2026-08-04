import { Component, input } from '@angular/core';

import { BadgeComponent } from '../badge/badge.component';
import { ButtonComponent } from '../button/button.component';
import { CardComponent } from '../card/card.component';
import { IconCheck } from '../icons/icons';

@Component({
  selector: 'app-pricing-tier',
  standalone: true,
  imports: [CardComponent, BadgeComponent, ButtonComponent, IconCheck],
  host: { class: 'block h-full' },
  template: `
    <app-card [variant]="highlighted() ? 'gradient' : 'default'">
      @if (highlighted()) {
        <app-badge variant="accent" class="mb-4 inline-flex w-fit">Most popular</app-badge>
      }
      <h3 class="text-lg font-semibold text-ink">{{ name() }}</h3>
      <p class="mt-3 flex items-baseline gap-1">
        <span class="text-4xl font-bold tracking-tight text-ink">{{ price() }}</span>
        @if (period()) {
          <span class="text-sm text-ink-muted">{{ period() }}</span>
        }
      </p>
      <p class="mt-2 text-sm text-ink-muted">{{ tagline() }}</p>

      <ul class="mt-6 flex-1 space-y-3 text-sm text-ink-muted">
        @for (feature of features(); track feature) {
          <li class="flex items-start gap-2">
            <app-icon-check [size]="16" class="mt-0.5 shrink-0 text-accent-bright" />
            <span>{{ feature }}</span>
          </li>
        }
      </ul>

      <a appButton [variant]="highlighted() ? 'primary' : 'secondary'" href="#submit" class="mt-8 w-full justify-center">
        {{ ctaLabel() }}
      </a>
    </app-card>
  `,
})
export class PricingTierComponent {
  readonly name = input.required<string>();
  readonly price = input.required<string>();
  readonly period = input('');
  readonly tagline = input('');
  readonly features = input<string[]>([]);
  readonly highlighted = input(false);
  readonly ctaLabel = input('Get Started');
}
