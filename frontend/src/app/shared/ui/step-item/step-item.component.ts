import { Component, computed, input } from '@angular/core';

import { IconCheck } from '../icons/icons';

export type StepStatus = 'done' | 'active' | 'pending';
export type StepOrientation = 'vertical' | 'horizontal';

@Component({
  selector: 'li[appStepItem]',
  standalone: true,
  imports: [IconCheck],
  host: {
    '[class]': 'hostClasses()',
  },
  template: `
    @if (orientation() === 'horizontal' && !last()) {
      <div [class]="lineClasses()"></div>
    }
    <div class="relative flex h-9 w-9 shrink-0 items-center justify-center">
      @if (status() === 'active') {
        <span
          class="absolute -inset-1 animate-spin rounded-full border-2 border-accent/40 border-t-accent"
        ></span>
      }
      <div [class]="circleClasses()">
        @if (status() === 'done') {
          <app-icon-check [size]="16" />
        } @else if (status() === 'active') {
          <span class="h-2.5 w-2.5 animate-pulse rounded-full bg-white"></span>
        } @else {
          {{ index() }}
        }
      </div>
    </div>
    <div [class]="labelWrapClasses()">
      <p class="text-sm font-semibold text-ink">{{ label() }}</p>
      @if (status() === 'active') {
        <p class="text-sm text-accent-bright">{{ subStatus() }}</p>
      } @else {
        <p [class]="descriptionClasses()">{{ description() }}</p>
      }
    </div>
  `,
})
export class StepItemComponent {
  readonly index = input.required<number>();
  readonly label = input.required<string>();
  readonly description = input.required<string>();
  readonly subStatus = input('');
  readonly status = input<StepStatus>('pending');
  readonly orientation = input<StepOrientation>('vertical');
  readonly last = input(false);

  protected readonly hostClasses = computed(() =>
    this.orientation() === 'horizontal'
      ? 'relative flex flex-1 flex-col items-center text-center'
      : 'flex items-center gap-4'
  );

  protected readonly labelWrapClasses = computed(() =>
    this.orientation() === 'horizontal' ? 'mt-2.5 max-w-[9rem]' : ''
  );

  protected readonly descriptionClasses = computed(() =>
    this.orientation() === 'horizontal' ? 'hidden text-xs text-ink-muted sm:block' : 'text-sm text-ink-muted'
  );

  protected readonly lineClasses = computed(() => {
    const base = 'absolute left-1/2 top-[18px] -z-10 h-0.5 w-full';
    return this.status() === 'done' ? `${base} bg-accent` : `${base} bg-border-card`;
  });

  protected readonly circleClasses = computed(() => {
    const base = 'flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold';
    const byStatus: Record<StepStatus, string> = {
      done: 'bg-success text-white',
      active: 'bg-gradient-to-br from-accent to-accent-bright text-white shadow-cta-glow',
      pending: 'border border-border-card bg-white/5 text-ink-muted',
    };
    return `${base} ${byStatus[this.status()]}`;
  });
}
