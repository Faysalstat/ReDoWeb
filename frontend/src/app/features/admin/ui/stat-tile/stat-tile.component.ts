import { Component, computed, input } from '@angular/core';

export type StatTileVariant = 'default' | 'accent' | 'danger';

/** A single KPI cell for the admin dashboard grid -- label, big value,
 * optional trend note. Matches the `.cell`/`.metric__num` pattern used by
 * every other stats strip in the app (home hero stats, admin KPI strip). */
@Component({
  selector: 'app-stat-tile',
  standalone: true,
  host: { class: 'cell' },
  template: `
    <p [class]="valueClasses()">{{ value() }}</p>
    <p class="metric__label">{{ label() }}</p>
    @if (note(); as n) {
      <p class="metric__note">{{ n }}</p>
    }
  `,
  styles: [
    `
      .metric__note {
        margin: var(--space-1) 0 0;
        font-size: 11px;
        color: var(--color-neutral-600);
      }
    `,
  ],
})
export class StatTileComponent {
  readonly label = input.required<string>();
  readonly value = input.required<string | number>();
  readonly note = input<string | null>(null);
  readonly variant = input<StatTileVariant>('default');

  protected readonly valueClasses = computed(() => {
    const variants: Record<StatTileVariant, string> = {
      default: 'metric__num',
      accent: 'metric__num metric__num--accent',
      danger: 'metric__num metric__num--accent',
    };
    return variants[this.variant()];
  });
}
