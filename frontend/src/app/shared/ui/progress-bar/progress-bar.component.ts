import { Component, input } from '@angular/core';

/** Slim rounded gradient progress bar -- reused on the generation progress
 * page and as the inline mini-bar on in-progress History rows. */
@Component({
  selector: 'app-progress-bar',
  standalone: true,
  host: { class: 'block h-1.5 w-full overflow-hidden rounded-full bg-border-card/60' },
  template: `
    <div
      class="animate-shimmer h-full rounded-full bg-gradient-to-r from-accent via-accent-teal to-accent transition-[width] duration-700 ease-out"
      [style.width.%]="percent()"
    ></div>
  `,
})
export class ProgressBarComponent {
  readonly percent = input(0);
}
