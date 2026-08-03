import { Directive, ElementRef, HostListener, OnInit, inject } from '@angular/core';

@Directive({
  selector: '[appParallaxHero]',
  standalone: true,
  host: { class: 'parallax-hero' },
})
export class ParallaxHeroDirective implements OnInit {
  private readonly host = inject(ElementRef<HTMLElement>);
  private reducedMotion = false;

  ngOnInit(): void {
    this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!this.reducedMotion) {
      this.update();
    }
  }

  @HostListener('window:scroll')
  onScroll(): void {
    if (this.reducedMotion) {
      return;
    }
    this.update();
  }

  private update(): void {
    const viewportHeight = window.innerHeight || 1;
    const progress = Math.min(Math.max(window.scrollY / (viewportHeight * 0.5), 0), 1);
    const style = this.host.nativeElement.style;
    style.setProperty('--parallax-opacity', `${1 - progress}`);
    style.setProperty('--parallax-scale', `${1 - progress * 0.05}`);
    style.setProperty('--parallax-y', `${progress * 100}px`);
  }
}
