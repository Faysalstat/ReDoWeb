import { Component, computed, input } from '@angular/core';

export type IconContainerTone = 'accent' | 'neutral' | 'success';

@Component({
  selector: 'app-icon-container',
  standalone: true,
  host: { class: 'block' },
  template: `<div [class]="classes()"><ng-content /></div>`,
})
export class IconContainerComponent {
  readonly tone = input<IconContainerTone>('neutral');

  protected readonly classes = computed(() => {
    const base = 'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border text-sm font-bold';
    const tones: Record<IconContainerTone, string> = {
      accent: 'border-accent/30 bg-gradient-to-br from-accent to-accent-bright text-white shadow-cta-glow',
      neutral: 'border-white/10 bg-white/5 text-ink',
      success: 'border-emerald-500/30 bg-emerald-500 text-white',
    };
    return `${base} ${tones[this.tone()]}`;
  });
}
