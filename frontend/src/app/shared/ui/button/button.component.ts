import { Component, computed, input } from '@angular/core';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost';
export type ButtonShape = 'rect' | 'pill';

@Component({
  selector: 'button[appButton], a[appButton]',
  standalone: true,
  template: `
    <span class="btn-shine" aria-hidden="true"></span>
    <span class="relative z-10 inline-flex items-center gap-2">
      <ng-content />
    </span>
  `,
  host: {
    '[class]': 'hostClasses()',
  },
})
export class ButtonComponent {
  readonly variant = input<ButtonVariant>('primary');
  readonly shape = input<ButtonShape>('rect');

  protected readonly hostClasses = computed(() => {
    const base =
      'group relative inline-flex items-center justify-center overflow-hidden px-6 py-3 text-sm font-semibold transition-all duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100';
    const shapes: Record<ButtonShape, string> = {
      rect: 'rounded-lg',
      pill: 'rounded-full',
    };
    const variants: Record<ButtonVariant, string> = {
      primary:
        'bg-accent text-white shadow-cta-glow hover:bg-accent-bright disabled:bg-white/10 disabled:text-ink-muted disabled:shadow-none',
      secondary:
        'bg-white/5 text-ink shadow-inset-highlight hover:bg-white/8 disabled:bg-white/5 disabled:text-ink-muted',
      ghost: 'bg-transparent text-ink-muted hover:bg-white/5 hover:text-ink disabled:text-ink-muted/50',
    };
    return `${base} ${shapes[this.shape()]} ${variants[this.variant()]}`;
  });
}
