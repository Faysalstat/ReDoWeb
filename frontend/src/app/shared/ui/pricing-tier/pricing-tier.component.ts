import { Component, computed, input } from '@angular/core';

import { RouterLink } from '@angular/router';

import { ButtonComponent } from '../button/button.component';

export type PricingTierTone = 'accent-2';

@Component({
  selector: 'app-pricing-tier',
  standalone: true,
  imports: [ButtonComponent, RouterLink],
  host: { style: 'display: block; height: 100%' },
  template: `
    <div class="plan" [style.background]="cardBackground()" [style.borderColor]="cardBorderColor()" [style.boxShadow]="cardShadow()">
      @if (highlighted()) {
        <span class="plan__ribbon">Most popular</span>
      }

      <div>
        <h3 class="plan__name">{{ name() }}</h3>
        <p class="plan__blurb">{{ tagline() }}</p>
      </div>

      <p class="plan__price" [style.color]="priceColor()">
        {{ price() }}
        @if (period()) {
          <small>{{ period() }}</small>
        }
      </p>

      <a
        appButton
        variant="secondary"
        [routerLink]="ctaLink()"
        [queryParams]="ctaQueryParams()"
        class="btn-block plan__cta"
        [style.background]="ctaBackground()"
        [style.borderColor]="ctaBorderColor()"
        [style.color]="ctaColor()"
      >
        {{ ctaLabel() }}
      </a>

      <div class="plan__features">
        @for (feature of features(); track feature; let i = $index) {
          <div class="plan__feature">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" [style.marginTop.px]="3">
              <path
                d="M5 13l4 4L19 7"
                [attr.stroke]="checkColor(i)"
                stroke-width="2.4"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
            <span>{{ feature }}</span>
          </div>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .plan {
        position: relative;
        height: 100%;
        padding: 30px;
        display: flex;
        flex-direction: column;
        gap: 20px;
        border: 1px solid var(--color-divider);
        border-radius: 18px;
      }
      .plan__ribbon {
        position: absolute;
        top: -12px;
        left: 30px;
        background: var(--color-accent);
        color: #ffffff;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 5px 12px;
        border-radius: 999px;
      }
      .plan__name {
        font-size: 19px;
        font-weight: 700;
        margin: 0;
      }
      .plan__blurb {
        font-size: 13.5px;
        line-height: 21px;
        color: var(--color-neutral-700);
        margin: 8px 0 0;
      }
      .plan__price {
        font-family: var(--font-heading);
        font-weight: var(--font-heading-weight);
        font-size: 36px;
        line-height: 1;
        margin: 0;
        display: flex;
        align-items: baseline;
        gap: 6px;
        font-feature-settings: 'tnum' 1;
      }
      .plan__price small {
        font-size: 13px;
        font-weight: 500;
        color: var(--color-neutral-600);
      }
      .plan__cta {
        height: 46px;
        border-radius: 10px;
        font-size: 14px;
        justify-content: center;
      }
      .plan__features {
        display: flex;
        flex-direction: column;
        gap: 11px;
        border-top: 1px solid var(--color-divider);
        padding-top: 6px;
      }
      .plan__feature {
        display: flex;
        gap: 9px;
        align-items: flex-start;
        font-size: 13.5px;
        line-height: 22px;
        color: var(--color-neutral-700);
      }
      .plan__feature svg {
        flex: none;
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
  /** Where the CTA goes -- e.g. /checkout with ?pack=<id>. */
  readonly ctaLink = input<string>('/checkout');
  readonly ctaQueryParams = input<Record<string, string> | null>(null);
  readonly tone = input<PricingTierTone | undefined>(undefined);

  protected readonly cardBackground = computed(() =>
    this.highlighted()
      ? 'linear-gradient(165deg, color-mix(in srgb, var(--color-accent) 16%, var(--color-surface)), var(--color-surface) 75%)'
      : 'var(--color-surface)'
  );

  protected readonly cardBorderColor = computed(() => {
    if (this.highlighted()) {
      return 'color-mix(in srgb, var(--color-accent) 40%, transparent)';
    }
    if (this.tone() === 'accent-2') {
      return 'color-mix(in srgb, var(--color-accent-2) 40%, transparent)';
    }
    return 'var(--color-divider)';
  });

  protected readonly cardShadow = computed(() =>
    this.highlighted() ? '0 20px 50px color-mix(in srgb, var(--color-accent) 16%, transparent)' : 'none'
  );

  protected readonly priceColor = computed(() => (this.tone() === 'accent-2' ? 'var(--color-accent-2)' : null));

  protected readonly ctaBackground = computed(() => {
    if (this.highlighted()) {
      return 'var(--color-accent)';
    }
    if (this.tone() === 'accent-2') {
      return 'color-mix(in srgb, var(--color-accent-2) 14%, transparent)';
    }
    return 'var(--color-neutral-200)';
  });

  protected readonly ctaBorderColor = computed(() => {
    if (this.highlighted()) {
      return 'transparent';
    }
    if (this.tone() === 'accent-2') {
      return 'color-mix(in srgb, var(--color-accent-2) 40%, transparent)';
    }
    return 'var(--color-divider-strong)';
  });

  protected readonly ctaColor = computed(() => {
    if (this.highlighted()) {
      return 'var(--color-bg)';
    }
    if (this.tone() === 'accent-2') {
      return 'var(--color-accent-2)';
    }
    return 'var(--color-text)';
  });

  protected checkColor(index: number): string {
    if (this.highlighted()) {
      return 'var(--color-success)';
    }
    if (this.tone() === 'accent-2' && index === 0) {
      return 'var(--color-accent-2)';
    }
    return '#5b6072';
  }
}
