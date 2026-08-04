import { Component, computed, input } from '@angular/core';

import { SpotlightDirective } from '../../directives/spotlight.directive';

export type CardVariant = 'default' | 'glass' | 'gradient' | 'danger';

@Component({
  selector: 'app-card',
  standalone: true,
  imports: [SpotlightDirective],
  host: { class: 'block h-full' },
  template: `
    <div [class]="containerClasses()" [appSpotlight]="spotlight()">
      <div class="spotlight-content flex h-full flex-col">
        <ng-content />
      </div>
    </div>
  `,
})
export class CardComponent {
  readonly variant = input<CardVariant>('default');
  readonly spotlight = input(false);

  protected readonly containerClasses = computed(() => {
    const base =
      'flex h-full flex-col rounded-2xl border p-6 shadow-card transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] hover:shadow-card-hover sm:p-8';
    const variants: Record<CardVariant, string> = {
      default: 'border-border-card bg-canvas-elevated/60 hover:border-white/15',
      glass: 'border-border-card bg-canvas-elevated/40 backdrop-blur-xl hover:border-white/15',
      gradient: 'border-accent/30 bg-gradient-to-b from-accent/10 via-white/5 to-white/2 hover:border-accent/40',
      danger: 'border-error/30 bg-error/5 hover:border-error/40',
    };
    return `${base} ${variants[this.variant()]}`;
  });
}
