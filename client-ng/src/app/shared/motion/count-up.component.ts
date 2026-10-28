import { Component, DestroyRef, ElementRef, afterNextRender, inject, input, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';

/** Counts from 0 to `target` once the element scrolls into view. */
@Component({
  selector: 'app-count-up',
  standalone: true,
  imports: [DecimalPipe],
  template: `{{ value() | number }}{{ suffix() }}`,
})
export class CountUpComponent {
  readonly target = input.required<number>();
  readonly suffix = input('');
  readonly duration = input(2000);
  protected readonly value = signal(0);

  constructor() {
    const el = inject(ElementRef).nativeElement as HTMLElement;
    const destroyRef = inject(DestroyRef);
    afterNextRender(() => {
      const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      if (reduced || typeof IntersectionObserver === 'undefined') {
        this.value.set(this.target());
        return;
      }
      const io = new IntersectionObserver(
        ([e]) => {
          if (!e.isIntersecting) return;
          io.disconnect();
          const start = performance.now();
          const tick = (now: number) => {
            const t = Math.min(1, (now - start) / this.duration());
            this.value.set(Math.floor(this.target() * t));
            if (t < 1) requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        },
        { threshold: 0.3 },
      );
      io.observe(el);
      destroyRef.onDestroy(() => io.disconnect());
    });
  }
}
