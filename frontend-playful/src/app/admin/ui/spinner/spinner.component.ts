import { Component, computed, input } from '@angular/core';

export type SpinnerSize = 'sm' | 'lg';

/** Small circular spin indicator, reused in buttons, progress cards, and
 * preview loaders. */
@Component({
  selector: 'app-spinner',
  standalone: true,
  host: { style: 'display: inline-flex' },
  template: `<span [class]="sizeClass()" class="spinner"></span>`,
  styles: [
    `
      .spinner {
        display: inline-block;
        border-radius: 50%;
        border-style: solid;
        border-color: var(--color-divider);
        border-top-color: var(--color-accent);
        animation: spinner-spin 0.7s linear infinite;
      }
      .spinner--sm {
        width: 14px;
        height: 14px;
        border-width: 2px;
      }
      .spinner--lg {
        width: 28px;
        height: 28px;
        border-width: 3px;
      }
      @keyframes spinner-spin {
        to {
          transform: rotate(360deg);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .spinner {
          animation: none;
        }
      }
    `,
  ],
})
export class SpinnerComponent {
  readonly size = input<SpinnerSize>('sm');

  protected readonly sizeClass = computed(() => (this.size() === 'lg' ? 'spinner--lg' : 'spinner--sm'));
}
