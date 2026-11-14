import { Component, computed, input } from '@angular/core';

/** Brand logo (public/reedoo_logo.png, served from a 600px copy in
 * public/assets/reedoo-logo-600.png to keep the page light). The image is
 * 3:1 with a transparent background, so only the height is set. */
@Component({
  selector: 'app-logo',
  standalone: true,
  template: `
    <img
      src="/assets/reedoo-logo-600.png"
      alt="ReeDoo"
      class="block w-auto select-none"
      [style.height.px]="h()"
      draggable="false"
    />
  `,
})
export class LogoComponent {
  readonly size = input<'sm' | 'md' | 'lg'>('md');
  protected readonly h = computed(() => ({ sm: 36, md: 48, lg: 68 })[this.size()]);
}
