import { Component, computed, input } from '@angular/core';

import { BadgeComponent, BadgeVariant } from '../../../../shared/ui/badge/badge.component';
import { CardComponent } from '../../../../shared/ui/card/card.component';

export type StatTileVariant = 'default' | 'accent' | 'danger';

/** A single KPI card for the admin dashboard grid -- label, big value,
 * optional trend note. Composes the existing CardComponent/BadgeComponent
 * rather than reinventing chrome, matching every other shared/ui atom's
 * `variant input -> computed() class map` idiom. */
@Component({
  selector: 'app-stat-tile',
  standalone: true,
  imports: [CardComponent, BadgeComponent],
  template: `
    <app-card variant="glass">
      <div class="flex flex-col gap-2">
        <span class="text-sm font-medium text-ink-muted">{{ label() }}</span>
        <span [class]="valueClasses()">{{ value() }}</span>
        @if (note(); as n) {
          <app-badge [variant]="noteVariant()">{{ n }}</app-badge>
        }
      </div>
    </app-card>
  `,
})
export class StatTileComponent {
  readonly label = input.required<string>();
  readonly value = input.required<string | number>();
  readonly note = input<string | null>(null);
  readonly variant = input<StatTileVariant>('default');

  protected readonly valueClasses = computed(() => {
    const base = 'text-3xl font-bold tracking-tight';
    const variants: Record<StatTileVariant, string> = {
      default: 'text-ink',
      accent: 'text-accent-bright',
      danger: 'text-error',
    };
    return `${base} ${variants[this.variant()]}`;
  });

  protected readonly noteVariant = computed<BadgeVariant>(() =>
    this.variant() === 'danger' ? 'danger' : 'muted'
  );
}
