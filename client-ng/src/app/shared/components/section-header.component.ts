import { Component, input } from '@angular/core';

import { RevealDirective } from '../motion/reveal.directive';

/** Blueprint §7.3: optional eyebrow, centered H2, optional subtitle. */
@Component({
  selector: 'app-section-header',
  standalone: true,
  imports: [RevealDirective],
  host: { class: 'block' },
  template: `
    <div reveal class="text-center" [class]="subtitle() ? 'mb-16' : ''">
      @if (eyebrow()) {
        <span class="text-sm font-semibold text-primary uppercase tracking-wider block mb-4">{{ eyebrow() }}</span>
      }
      <h2 class="text-3xl sm:text-4xl font-black" [class]="subtitle() ? 'mb-4' : 'mb-16'">{{ title() }}</h2>
      @if (subtitle()) {
        <p class="text-muted-foreground max-w-xl mx-auto">{{ subtitle() }}</p>
      }
    </div>
  `,
})
export class SectionHeaderComponent {
  readonly eyebrow = input<string>();
  readonly title = input.required<string>();
  readonly subtitle = input<string>();
}
