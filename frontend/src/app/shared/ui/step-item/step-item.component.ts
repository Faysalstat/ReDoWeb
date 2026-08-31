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
    <div class="step-item__marker">
      @if (status() === 'active') {
        <span class="step-item__ring"></span>
      }
      <div [class]="circleClasses()">
        @if (status() === 'done') {
          <app-icon-check [size]="16" />
        } @else if (status() === 'active') {
          <span class="step-item__dot"></span>
        } @else {
          {{ index() }}
        }
      </div>
    </div>
    <div [class]="labelWrapClasses()">
      <p class="step-item__label">{{ label() }}</p>
      @if (status() === 'active') {
        <p class="step-item__substatus">{{ subStatus() }}</p>
      } @else {
        <p class="step-item__description">{{ description() }}</p>
      }
    </div>
  `,
  styles: [
    `
      li[appStepItem] {
        display: flex;
        align-items: center;
        gap: var(--space-4);
      }
      li[appStepItem].step-item--horizontal {
        position: relative;
        flex: 1;
        flex-direction: column;
        align-items: center;
        text-align: center;
      }
      .step-item__marker {
        position: relative;
        display: flex;
        height: 36px;
        width: 36px;
        flex: none;
        align-items: center;
        justify-content: center;
      }
      .step-item__line {
        position: absolute;
        left: 50%;
        top: 18px;
        z-index: -1;
        height: 2px;
        width: 100%;
        background: var(--color-divider);
      }
      .step-item__line--done {
        background: var(--color-accent);
      }
      .step-item__ring {
        position: absolute;
        inset: -4px;
        border-radius: 50%;
        border: 2px solid color-mix(in srgb, var(--color-accent) 35%, transparent);
        border-top-color: var(--color-accent);
        animation: step-item-spin 0.8s linear infinite;
      }
      @keyframes step-item-spin {
        to {
          transform: rotate(360deg);
        }
      }
      .step-item__circle {
        display: flex;
        height: 36px;
        width: 36px;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        font-size: 14px;
        font-weight: 700;
        color: var(--color-text);
      }
      .step-item__circle--done {
        background: var(--color-accent);
        color: var(--color-bg);
      }
      .step-item__circle--active {
        background: var(--color-bg);
        border: 2px solid var(--color-accent);
      }
      .step-item__circle--pending {
        border: 1.5px solid var(--color-divider);
        color: var(--color-neutral-600);
      }
      .step-item__dot {
        height: 8px;
        width: 8px;
        border-radius: 50%;
        background: var(--color-accent);
      }
      .step-item__label-wrap--horizontal {
        margin-top: 10px;
        max-width: 9rem;
      }
      .step-item__label {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
      }
      .step-item__substatus {
        margin: 2px 0 0;
        font-size: 13px;
        color: var(--color-accent-700);
      }
      .step-item__description {
        margin: 2px 0 0;
        font-size: 13px;
        color: var(--color-neutral-700);
      }
    `,
  ],
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
    this.orientation() === 'horizontal' ? 'step-item--horizontal' : ''
  );

  protected readonly labelWrapClasses = computed(() =>
    this.orientation() === 'horizontal' ? 'step-item__label-wrap--horizontal' : ''
  );

  protected readonly lineClasses = computed(() =>
    this.status() === 'done' ? 'step-item__line step-item__line--done' : 'step-item__line'
  );

  protected readonly circleClasses = computed(() => {
    const byStatus: Record<StepStatus, string> = {
      done: 'step-item__circle step-item__circle--done',
      active: 'step-item__circle step-item__circle--active',
      pending: 'step-item__circle step-item__circle--pending',
    };
    return byStatus[this.status()];
  });
}
