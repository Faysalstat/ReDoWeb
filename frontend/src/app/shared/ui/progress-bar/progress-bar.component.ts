import { Component, input } from '@angular/core';

/** Slim progress bar -- reused on the generation progress page and as the
 * inline mini-bar on in-progress History rows. */
@Component({
  selector: 'app-progress-bar',
  standalone: true,
  host: { style: 'display: block' },
  template: `
    <div class="meter">
      <div class="meter__fill" [style.width.%]="percent()"></div>
    </div>
  `,
})
export class ProgressBarComponent {
  readonly percent = input(0);
}
