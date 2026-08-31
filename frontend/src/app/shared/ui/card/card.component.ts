import { Component, computed, input } from '@angular/core';

export type CardVariant = 'default' | 'glass' | 'gradient' | 'danger';

@Component({
  selector: 'app-card',
  standalone: true,
  host: { style: 'display: block; height: 100%' },
  template: `
    <div class="card elev-sm" [style.border]="border()">
      <ng-content />
    </div>
  `,
  styles: [
    `
      .card {
        height: 100%;
      }
    `,
  ],
})
export class CardComponent {
  readonly variant = input<CardVariant>('default');

  protected readonly border = computed(() => {
    const borders: Record<CardVariant, string> = {
      default: 'none',
      glass: 'none',
      gradient: '2px solid var(--color-accent)',
      danger: '2px solid var(--color-accent-800)',
    };
    return borders[this.variant()];
  });
}
