import { Component, computed, input } from '@angular/core';

export type BadgeVariant = 'accent' | 'muted' | 'warning' | 'success' | 'danger';

@Component({
  selector: 'app-badge',
  standalone: true,
  template: `<span [class]="classes()"><ng-content /></span>`,
  styles: [
    `
      .tag-danger {
        display: inline-flex;
        align-items: center;
        font-size: 11px;
        letter-spacing: 0.02em;
        padding: 3px 10px;
        background: var(--color-accent-800);
        color: var(--color-bg);
      }
    `,
  ],
})
export class BadgeComponent {
  readonly variant = input<BadgeVariant>('accent');

  protected readonly classes = computed(() => {
    const variants: Record<BadgeVariant, string> = {
      accent: 'tag tag-accent',
      muted: 'tag tag-neutral',
      warning: 'tag tag-accent-2',
      success: 'tag tag-outline',
      danger: 'tag tag-danger',
    };
    return variants[this.variant()];
  });
}
