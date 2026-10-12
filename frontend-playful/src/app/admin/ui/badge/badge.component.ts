import { Component, computed, input } from '@angular/core';

export type BadgeVariant = 'accent' | 'muted' | 'warning' | 'success' | 'danger';

/** Status tag. Styled by admin-theme.css (`.tag*` under `.pg-admin`). */
@Component({
  selector: 'app-badge',
  standalone: true,
  template: `<span [class]="classes()"><ng-content /></span>`,
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
