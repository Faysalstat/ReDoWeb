import { Component, computed, input } from '@angular/core';

import { ButtonComponent } from '../button/button.component';

@Component({
  selector: 'app-pricing-tier',
  standalone: true,
  imports: [ButtonComponent],
  host: { style: 'display: block; height: 100%' },
  template: `
    <div class="plan" [style.borderTopColor]="edgeColor()">
      <div class="row" style="gap: var(--space-3)">
        <span class="label" style="font-weight: 600; color: var(--color-text)">{{ name() }}</span>
        @if (highlighted()) {
          <span class="tag tag-accent">Most popular</span>
        }
      </div>
      <p class="plan__price">
        {{ price() }}
        @if (period()) {
          <small> {{ period() }}</small>
        }
      </p>
      <p class="plan__blurb">{{ tagline() }}</p>
      <a appButton [variant]="highlighted() ? 'primary' : 'secondary'" href="#submit" class="btn-block">
        {{ ctaLabel() }}
      </a>
      <div class="plan__features">
        @for (feature of features(); track feature) {
          <div class="plan__feature"><span></span><span>{{ feature }}</span></div>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .plan {
        height: 100%;
        background: var(--color-bg);
        padding: var(--space-8) var(--space-6);
        display: flex;
        flex-direction: column;
        gap: var(--space-4);
        border-top: 6px solid var(--color-neutral-400);
      }
      .plan__price {
        font-family: var(--font-heading);
        font-weight: var(--font-heading-weight);
        font-size: 54px;
        line-height: 1;
        letter-spacing: -0.03em;
        margin: 0 0 0 -0.045em;
        font-feature-settings: 'tnum' 1;
      }
      .plan__price small {
        font-size: 15px;
        font-weight: 500;
        letter-spacing: 0;
        color: var(--color-neutral-700);
      }
      .plan__blurb {
        font-size: 15px;
        line-height: 26px;
        color: var(--color-neutral-800);
        margin: 0;
        min-height: 78px;
      }
      .plan__features {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
        border-top: 2px solid var(--color-divider);
        padding-top: var(--space-4);
      }
      .plan__feature {
        display: grid;
        grid-template-columns: 14px 1fr;
        gap: var(--space-3);
        align-items: start;
        font-size: 14.5px;
        line-height: 24px;
      }
      .plan__feature span:first-child {
        width: 8px;
        height: 8px;
        background: var(--color-accent);
        margin-top: 8px;
      }
      @media (max-width: 880px) {
        .plan__blurb {
          min-height: 0;
        }
      }
    `,
  ],
})
export class PricingTierComponent {
  readonly name = input.required<string>();
  readonly price = input.required<string>();
  readonly period = input('');
  readonly tagline = input('');
  readonly features = input<string[]>([]);
  readonly highlighted = input(false);
  readonly ctaLabel = input('Get Started');

  protected readonly edgeColor = computed(() =>
    this.highlighted() ? 'var(--color-accent)' : 'var(--color-neutral-400)'
  );
}
