import { Component, Input } from '@angular/core';

/**
 * The before/after wireframe used where no real screenshot exists (e.g. the
 * original site's "before" pane -- most third-party sites block being
 * iframed via X-Frame-Options/CSP, so this stands in instead). Swap for a
 * real <img>/<iframe> only where the source is known to be embeddable.
 */
@Component({
  selector: 'app-site-mock',
  standalone: true,
  template: `
    @if (variant === 'old') {
      <div class="mock mock--old" [style.minHeight.px]="height">
        <div class="mock__bar mock__bar--strong" style="height: 46px"></div>
        <div class="mock__bar" style="height: 110px"></div>
        <div class="row" style="gap: 8px">
          <div class="mock__bar" style="flex: 1; height: 70px"></div>
          <div class="mock__bar" style="flex: 1; height: 70px"></div>
          <div class="mock__bar" style="flex: 1; height: 70px"></div>
        </div>
        <div class="mock__bar" style="height: 9px; width: 94%"></div>
        <div class="mock__bar" style="height: 9px; width: 88%"></div>
        <div class="mock__bar" style="height: 9px; width: 91%"></div>
        <div class="mock__bar" style="height: 9px; width: 63%"></div>
        <div class="mock__bar mock__bar--strong" style="height: 34px; width: 40%; margin-top: auto"></div>
      </div>
    } @else {
      <div class="mock mock--new" [style.minHeight.px]="height">
        <div class="row" style="gap: 10px; border-bottom: 2px solid var(--color-text); padding-bottom: 10px">
          <div class="mock__bar mock__bar--ink" style="height: 12px; width: 78px"></div>
          <div class="mock__bar mock__bar--strong" style="height: 6px; width: 40px; margin-left: auto"></div>
          <div class="mock__bar mock__bar--accent" style="height: 20px; width: 56px"></div>
        </div>
        <div class="mock__bar mock__bar--accent" style="height: 7px; width: 30%"></div>
        <div class="mock__bar mock__bar--ink" style="height: 26px; width: 88%"></div>
        <div class="mock__bar mock__bar--ink" style="height: 26px; width: 62%"></div>
        <div class="mock__bar mock__bar--strong" style="height: 7px; width: 74%"></div>
        <div class="mock__bar mock__bar--strong" style="height: 7px; width: 68%"></div>
        <div class="row" style="gap: 10px">
          <div class="mock__bar mock__bar--accent" style="height: 30px; width: 120px"></div>
          <div style="height: 30px; width: 96px; border: 2px solid var(--color-text)"></div>
        </div>
        <div class="cells cells--3" style="margin-top: auto; background: transparent; gap: 10px">
          <div style="height: 52px; background: var(--color-neutral-200)"></div>
          <div style="height: 52px; background: var(--color-neutral-200)"></div>
          <div style="height: 52px; background: var(--color-neutral-200)"></div>
        </div>
      </div>
    }
  `,
})
export class SiteMockComponent {
  @Input() variant: 'old' | 'new' = 'new';
  @Input() height = 420;
}
