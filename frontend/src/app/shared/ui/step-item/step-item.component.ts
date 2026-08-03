import { Component, computed, input } from '@angular/core';

import { IconCheck } from '../icons/icons';

export type StepStatus = 'done' | 'active' | 'pending';

@Component({
  selector: 'li[appStepItem]',
  standalone: true,
  imports: [IconCheck],
  host: { class: 'flex items-center gap-4' },
  template: `
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
    <div>
      <p class="font-semibold text-ink">{{ label() }}</p>
      @if (status() === 'active') {
        <p class="text-sm text-accent-bright">{{ subStatus() }}</p>
      } @else {
        <p class="text-sm text-ink-muted">{{ description() }}</p>
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

  protected readonly circleClasses = computed(() => {
    const base = 'flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold';
    const byStatus: Record<StepStatus, string> = {
      done: 'bg-emerald-500 text-white',
      active: 'bg-gradient-to-br from-accent to-accent-bright text-white shadow-cta-glow',
      pending: 'border border-white/10 bg-white/5 text-ink-muted',
    };
    return `${base} ${byStatus[this.status()]}`;
  });
}
