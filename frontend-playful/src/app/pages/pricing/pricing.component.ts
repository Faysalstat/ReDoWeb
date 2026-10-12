import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { IconChevronDown } from '../../ui/icons';
import { PgPackGridComponent } from '../../ui/pack-grid.component';

/** Public /pricing: real admin-configured credit packs (PgPackGridComponent)
 * plus an FAQ restating how credits are spent. */
@Component({
  selector: 'pg-pricing',
  standalone: true,
  imports: [RouterLink, PgPackGridComponent, IconChevronDown],
  template: `
    <section class="pr__hero">
      <span class="pg-shape pr__sun pg-shape--hide-sm" aria-hidden="true"></span>
      <span class="pg-shape pr__tri pg-float pg-shape--hide-sm" aria-hidden="true"></span>
      <div class="pg-wrap pr__head">
        <span class="pg-kicker">Pricing</span>
        <h1 class="pr__title">Preview for free. <span class="pg-squiggle" style="--pg-squiggle-color: var(--pg-amber)">Pay</span> only for what you keep.</h1>
        <p class="pr__sub pg-muted">
          Every tier comes with a free live preview. Buy a credit pack once (no subscriptions) and spend credits only on
          the redesigns you want to download.
        </p>
      </div>
    </section>

    <section class="pg-section pr__packs pg-dots">
      <div class="pg-wrap">
        <pg-pack-grid />
      </div>
    </section>

    <section class="pg-section">
      <div class="pg-wrap pr__faq-wrap">
        <h2 class="pr__faq-title">Questions, answered</h2>
        <div class="pr__faq">
          @for (q of faq; track q.q) {
            <details class="pg-card pr__q">
              <summary>
                <span>{{ q.q }}</span>
                <span class="pg-icon-badge pg-icon-badge--amber pr__chev" aria-hidden="true"><app-icon-chevron-down [size]="16" /></span>
              </summary>
              <p class="pg-muted">{{ q.a }}</p>
            </details>
          }
        </div>
        <a class="pg-btn" routerLink="/">Try it with your site</a>
      </div>
    </section>
  `,
  styles: [
    `
      .pr__hero { position: relative; overflow: hidden; padding: 72px 0 56px; border-bottom: 2px solid var(--pg-fg); }
      .pr__head { position: relative; display: grid; justify-items: center; text-align: center; gap: 18px; }
      .pr__title { font-size: clamp(2.2rem, 5vw, var(--pg-text-5xl)); max-width: 18ch; }
      .pr__sub { max-width: 58ch; font-size: var(--pg-text-lg); }
      .pr__sun { width: 280px; height: 280px; border-radius: 50%; background: var(--pg-amber); border: 2px solid var(--pg-fg); right: -80px; top: -90px; }
      .pr__tri { width: 0; height: 0; left: 8%; bottom: 40px; border-left: 28px solid transparent; border-right: 28px solid transparent; border-bottom: 48px solid var(--pg-pink); }
      .pr__packs { border-bottom: 2px solid var(--pg-fg); }
      .pr__faq-wrap { display: grid; justify-items: center; gap: 32px; }
      .pr__faq-title { font-size: clamp(1.8rem, 4vw, var(--pg-text-3xl)); }
      .pr__faq { width: 100%; max-width: 760px; display: grid; gap: 16px; }
      .pr__q { padding: 0; box-shadow: var(--pg-pop-active); }
      .pr__q summary { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 22px; cursor: pointer; list-style: none; font: 700 var(--pg-text-lg) / 1.3 var(--pg-font-heading); }
      .pr__q summary::-webkit-details-marker { display: none; }
      .pr__q p { padding: 0 22px 20px; }
      .pr__chev { --_size: 34px; box-shadow: none; transition: transform 300ms var(--pg-bounce); }
      .pr__q[open] .pr__chev { transform: rotate(180deg); }
    `,
  ],
})
export class PricingComponent {
  readonly faq = [
    {
      q: 'What does the preview cost?',
      a: 'Nothing to look at. Starting a redesign spends 1 credit, and you can then browse every tier’s live preview for free.',
    },
    {
      q: 'When do I spend credits?',
      a: 'When you buy a tier’s design. That unlocks the ZIP download and, depending on the tier, generating the rest of your pages and running the SEO agent at no extra charge.',
    },
    {
      q: 'Is this a subscription?',
      a: 'No. Credit packs are one-time purchases. Credits stay in your wallet until you use them.',
    },
    {
      q: 'Do I pay again to re-download?',
      a: 'No. Once you’ve bought a tier’s design you can download it again from your History any time, free.',
    },
    {
      q: 'How can I pay?',
      a: 'With a PayPal account or any debit or credit card through PayPal. ReDoWebs never sees your card details.',
    },
  ];
}
