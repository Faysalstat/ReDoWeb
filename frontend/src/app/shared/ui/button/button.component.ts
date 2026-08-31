import { Component, computed, input } from '@angular/core';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost';

@Component({
  selector: 'button[appButton], a[appButton]',
  standalone: true,
  template: `<ng-content />`,
  host: {
    '[class]': 'hostClasses()',
  },
})
export class ButtonComponent {
  readonly variant = input<ButtonVariant>('primary');

  protected readonly hostClasses = computed(() => {
    const variants: Record<ButtonVariant, string> = {
      primary: 'btn btn-primary',
      secondary: 'btn btn-secondary',
      ghost: 'btn btn-ghost',
    };
    return variants[this.variant()];
  });
}
