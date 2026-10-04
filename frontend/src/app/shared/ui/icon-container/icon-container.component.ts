import { Component, computed, input } from '@angular/core';

export type IconContainerTone = 'accent' | 'neutral' | 'success';

@Component({
  selector: 'app-icon-container',
  standalone: true,
  host: { style: 'display: block' },
  template: `<div [class]="classes()"><ng-content /></div>`,
  styles: [
    `
      .icon-container {
        display: flex;
        height: 40px;
        width: 40px;
        flex: none;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 700;
      }
      .icon-container--accent {
        background: var(--color-accent-100);
        color: var(--color-accent-700);
      }
      .icon-container--neutral {
        background: var(--color-neutral-200);
        color: var(--color-text);
      }
      .icon-container--success {
        border: 2px solid var(--color-accent);
        color: var(--color-accent);
      }
    `,
  ],
})
export class IconContainerComponent {
  readonly tone = input<IconContainerTone>('neutral');

  protected readonly classes = computed(() => {
    const tones: Record<IconContainerTone, string> = {
      accent: 'icon-container icon-container--accent',
      neutral: 'icon-container icon-container--neutral',
      success: 'icon-container icon-container--success',
    };
    return tones[this.tone()];
  });
}
