import { Component } from '@angular/core';

/** The playful brand mark: three primitive shapes leaning on each other. */
@Component({
  selector: 'pg-logo',
  standalone: true,
  host: { class: 'pg-logo' },
  template: `
    <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true">
      <rect x="15" y="15" width="16" height="16" rx="3" fill="#F472B6" stroke="#1E293B" stroke-width="2" transform="rotate(12 23 23)" />
      <path d="M10 3 L19 18 H1 Z" fill="#FBBF24" stroke="#1E293B" stroke-width="2" stroke-linejoin="round" />
      <circle cx="11" cy="23" r="8" fill="#8B5CF6" stroke="#1E293B" stroke-width="2" />
    </svg>
    <span class="pg-logo__word">ReDo<span>Webs</span></span>
  `,
  styles: [
    `
      :host {
        display: inline-flex;
        align-items: center;
        gap: 10px;
      }
      .pg-logo__word {
        font: 800 1.35rem/1 var(--pg-font-heading);
        letter-spacing: -0.03em;
        color: var(--pg-fg);
      }
      .pg-logo__word span {
        color: var(--pg-accent);
      }
    `,
  ],
})
export class PgLogoComponent {}
