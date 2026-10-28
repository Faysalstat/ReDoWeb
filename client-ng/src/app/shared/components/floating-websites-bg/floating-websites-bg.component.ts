import { Component, ViewEncapsulation, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

import { MINI_SITES } from './mini-sites';

const CARD_COUNT = 20;

/** Fixed, non-interactive layer of 20 tiny "website screenshot" cards
 * drifting across the screen at 12% opacity (blueprint §7.18). Four shared
 * keyframes driven by CSS variables instead of one per card. Hidden entirely
 * under prefers-reduced-motion. Content above it needs `relative z-10`. */
@Component({
  selector: 'app-floating-websites-bg',
  standalone: true,
  // Unencapsulated: emulated encapsulation renames @keyframes, which breaks
  // the animation names chosen at runtime through --anim. Names are prefixed instead.
  encapsulation: ViewEncapsulation.None,
  styles: [
    `
      @keyframes fwb-drift-left { from { transform: translateX(120vw) rotate(var(--rot)); } to { transform: translateX(-300px) rotate(var(--rot)); } }
      @keyframes fwb-drift-right { from { transform: translateX(-300px) rotate(var(--rot)); } to { transform: translateX(120vw) rotate(var(--rot)); } }
      @keyframes fwb-drift-up { from { transform: translateY(110vh) rotate(var(--rot)); } to { transform: translateY(-150px) rotate(var(--rot)); } }
      @keyframes fwb-drift-down { from { transform: translateY(-150px) rotate(var(--rot)); } to { transform: translateY(110vh) rotate(var(--rot)); } }
      .fwb-layer { position: fixed; inset: 0; overflow: hidden; z-index: 0; pointer-events: none; }
      .fwb-card {
        position: absolute; width: 160px; height: 110px; border-radius: 10px; overflow: hidden; opacity: 0.12;
        box-shadow: 0 6px 28px rgba(0, 0, 0, 0.45); border: 1px solid rgba(255, 255, 255, 0.07);
        animation: var(--anim) var(--dur) linear var(--delay) infinite;
        will-change: transform;
      }
      @media (prefers-reduced-motion: reduce) { app-floating-websites-bg { display: none; } }
    `,
  ],
  template: `
    <div class="fwb-layer" aria-hidden="true">
      @for (c of cards; track c.key) {
        <div
          class="fwb-card"
          [style.top]="c.horizontal ? c.cross + '%' : '0'"
          [style.left]="c.horizontal ? '0' : c.cross + '%'"
          [style.--rot]="c.rot + 'deg'"
          [style.--anim]="'fwb-drift-' + c.dir"
          [style.--dur]="c.dur + 's'"
          [style.--delay]="c.delay + 's'"
          [innerHTML]="sites[c.tpl]"
        ></div>
      }
    </div>
  `,
})
export class FloatingWebsitesBgComponent {
  private readonly sanitizer = inject(DomSanitizer);

  // App-authored constants only (see mini-sites.ts), so trusting them is safe.
  protected readonly sites: SafeHtml[] = MINI_SITES.map((html) => this.sanitizer.bypassSecurityTrustHtml(html));

  protected readonly cards = Array.from({ length: CARD_COUNT }, (_, i) => {
    const dir = (['left', 'right', 'up', 'down'] as const)[i % 4];
    const dur = 32 + Math.random() * 26;
    return {
      key: i,
      dir,
      horizontal: dir === 'left' || dir === 'right',
      tpl: i % MINI_SITES.length,
      rot: Math.random() * 10 - 5,
      cross: 4 + (i / CARD_COUNT) * 88 + (Math.random() * 5 - 2.5),
      dur,
      delay: -(Math.random() * dur),
    };
  });
}
