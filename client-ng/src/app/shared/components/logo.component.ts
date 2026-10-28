import { Component, computed, input } from '@angular/core';

/** Blueprint §7.1 logo, adapted to the ReDoWebs name: red circle with a
 * serif "R", then the wordmark with R in red and D in green. */
@Component({
  selector: 'app-logo',
  standalone: true,
  template: `
    <span class="inline-flex items-center" [style.gap.px]="8 * s()">
      <span
        class="flex items-center justify-center shrink-0 rounded-full"
        [style.width.px]="34 * s()"
        [style.height.px]="34 * s()"
        style="background: #e52222; box-shadow: 0 2px 8px rgba(229, 34, 34, 0.45)"
      >
        <span
          style="color: #fff; font-weight: 900; line-height: 1; font-family: Georgia, serif; letter-spacing: -0.02em"
          [style.font-size.px]="22 * s()"
          >R</span
        >
      </span>
      <span
        class="flex items-baseline"
        style="font-family: Georgia, 'Times New Roman', serif; letter-spacing: -0.01em; line-height: 1"
        [style.font-size.px]="22 * s()"
      >
        <span style="color: #e52222; font-weight: 900">R</span><span class="text-foreground font-bold">e</span
        ><span style="color: #22c55e; font-weight: 900">D</span><span class="text-foreground font-bold">oWebs</span>
      </span>
    </span>
  `,
})
export class LogoComponent {
  readonly size = input<'sm' | 'md' | 'lg'>('md');
  protected readonly s = computed(() => ({ sm: 0.75, md: 1, lg: 1.4 })[this.size()]);
}
