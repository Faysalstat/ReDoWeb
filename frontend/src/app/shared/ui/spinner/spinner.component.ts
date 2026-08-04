import { Component, computed, input } from '@angular/core';

export type SpinnerSize = 'sm' | 'lg';

/** Small circular border-spin spinner, reused in buttons, progress cards,
 * and preview loaders. */
@Component({
  selector: 'app-spinner',
  standalone: true,
  host: { class: 'inline-flex' },
  template: `<span [class]="classes()"></span>`,
})
export class SpinnerComponent {
  readonly size = input<SpinnerSize>('sm');

  protected readonly classes = computed(() => {
    const base = 'animate-spin rounded-full border-white/20 border-t-white';
    const sizes: Record<SpinnerSize, string> = {
      sm: 'h-3.5 w-3.5 border-2',
      lg: 'h-7 w-7 border-[3px]',
    };
    return `${base} ${sizes[this.size()]}`;
  });
}
