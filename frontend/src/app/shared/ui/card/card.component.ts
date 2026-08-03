import { Component, computed, input } from '@angular/core';

import { SpotlightDirective } from '../../directives/spotlight.directive';

export type CardVariant = 'default' | 'glass' | 'gradient';

@Component({
  selector: 'app-card',
  standalone: true,
  imports: [SpotlightDirective],
  host: { class: 'block' },
  template: `
    <div [class]="containerClasses()" [appSpotlight]="spotlight()">
      <div class="spotlight-content">
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
      'rounded-2xl border border-white/6 p-6 shadow-card transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] hover:shadow-card-hover hover:border-white/10 sm:p-8';
    const variants: Record<CardVariant, string> = {
      default: 'bg-white/5',
      glass: 'bg-white/5 backdrop-blur-xl',
      gradient: 'bg-gradient-to-b from-white/8 to-white/2',
    };
    return `${base} ${variants[this.variant()]}`;
  });
}
