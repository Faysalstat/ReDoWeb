import { Component, computed, input } from '@angular/core';

export type BadgeVariant = 'accent' | 'muted' | 'warning';

@Component({
  selector: 'app-badge',
  standalone: true,
  template: `<span [class]="classes()"><ng-content /></span>`,
})
export class BadgeComponent {
  readonly variant = input<BadgeVariant>('accent');

  protected readonly classes = computed(() => {
    const base =
      'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide';
    const variants: Record<BadgeVariant, string> = {
      accent: 'border-accent/30 bg-accent/10 text-accent-bright',
      muted: 'border-white/10 bg-white/5 text-ink-muted normal-case tracking-normal',
      warning: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    };
    return `${base} ${variants[this.variant()]}`;
  });
}
