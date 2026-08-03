import { Directive, ElementRef, HostListener, inject, input } from '@angular/core';

@Directive({
  selector: '[appSpotlight]',
  standalone: true,
  host: { class: 'spotlight-surface' },
})
export class SpotlightDirective {
  private readonly host = inject(ElementRef<HTMLElement>);

  /** Whether the mouse-tracking glow is active; the class is always present so the pseudo-element exists, but tracking only runs when enabled. */
  readonly appSpotlight = input(true);

  @HostListener('mousemove', ['$event'])
  onMouseMove(event: MouseEvent): void {
    if (!this.appSpotlight()) {
      return;
    }
    const rect = this.host.nativeElement.getBoundingClientRect();
    const style = this.host.nativeElement.style;
    style.setProperty('--spot-x', `${event.clientX - rect.left}px`);
    style.setProperty('--spot-y', `${event.clientY - rect.top}px`);
    style.setProperty('--spot-opacity', '1');
  }

  @HostListener('mouseleave')
  onMouseLeave(): void {
    this.host.nativeElement.style.setProperty('--spot-opacity', '0');
  }
}
