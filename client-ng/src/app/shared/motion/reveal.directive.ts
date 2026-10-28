import { DestroyRef, Directive, ElementRef, afterNextRender, inject, input } from '@angular/core';

/**
 * <div reveal>                       fade-up 20px when scrolled into view (once)
 * <div reveal [revealDelay]="i*80">  staggered
 * <div reveal revealFrom="scale">    scale 0.9 -> 1 (badges, pills, counters)
 */
@Directive({
  selector: '[reveal]',
  standalone: true,
  host: {
    class: 'reveal',
    '[style.--reveal-delay]': 'revealDelay() + "ms"',
    '[style.--reveal-y]': 'revealFrom() === "scale" ? "0px" : revealY() + "px"',
    '[style.--reveal-scale]': 'revealFrom() === "scale" ? 0.9 : 1',
  },
})
export class RevealDirective {
  readonly revealDelay = input(0);
  readonly revealY = input(20);
  readonly revealFrom = input<'up' | 'scale'>('up');

  constructor() {
    const el = inject(ElementRef<HTMLElement>).nativeElement as HTMLElement;
    const destroyRef = inject(DestroyRef);

    afterNextRender(() => {
      if (typeof IntersectionObserver === 'undefined') {
        el.classList.add('is-visible');
        return;
      }
      const io = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            el.classList.add('is-visible');
            io.disconnect();
          }
        },
        { threshold: 0.15 },
      );
      io.observe(el);
      destroyRef.onDestroy(() => io.disconnect());
    });
  }
}
