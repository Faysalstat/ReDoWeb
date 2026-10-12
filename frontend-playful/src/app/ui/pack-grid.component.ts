import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { CreditPack, PublicTier } from '../core/redowebs-api.models';
import { RedoWebsApiService } from '../core/redowebs-api.service';
import { IconArrowRight, IconCheck, IconStar } from './icons';

export function formatUsd(cents: number): string {
  return cents % 100 === 0 ? `$${cents / 100}` : `$${(cents / 100).toFixed(2)}`;
}

/** Admin-configured credit packs plus each tier's download cost, from the
 * public GET /billing/credit-packs and GET /tiers endpoints. With three
 * or more packs the middle one is scaled up and gets a rotated star badge
 * naming the biggest tier it pays for -- a fact about the pack, not an
 * invented "most popular" claim. */
@Component({
  selector: 'pg-pack-grid',
  standalone: true,
  imports: [RouterLink, IconArrowRight, IconCheck, IconStar],
  template: `
    @if (loading()) {
      <p class="pg-muted">Loading prices…</p>
    } @else if (error()) {
      <p class="pg-muted">Prices couldn't be loaded right now. Please try again shortly.</p>
    } @else if (packs().length === 0) {
      <p class="pg-muted">Credit packs aren't on sale yet. Check back soon. Previews are always free.</p>
    } @else {
      <div class="ppg">
        @for (pack of packs(); track pack.id; let i = $index) {
          @let featured = isFeatured(i);
          <article class="pg-card ppg__card" [class.pg-card--featured]="featured" [class.ppg__card--featured]="featured">
            @if (featured && topTier(pack); as tier) {
              <div class="ppg__star">
                <app-icon-star [size]="16" />
                <span>Unlocks<br /><b>{{ tier }}</b></span>
              </div>
            }
            <span [class]="badgeClass(i)">
              <span class="ppg__credits">{{ pack.credits }}</span>
            </span>
            <h3 class="ppg__name">{{ pack.name }}</h3>
            <p class="ppg__price">
              <span>{{ price(pack) }}</span>
              <small>one-time</small>
            </p>
            <ul class="ppg__features">
              @for (f of features(pack); track f) {
                <li>
                  <span class="pg-icon-badge pg-icon-badge--mint ppg__tick"><app-icon-check [size]="12" /></span>
                  {{ f }}
                </li>
              }
            </ul>
            <a
              class="pg-btn pg-btn--block"
              [class.pg-btn--secondary]="!featured"
              routerLink="/checkout"
              [queryParams]="{ pack: pack.id }"
            >
              Buy {{ pack.credits }} credits
              @if (featured) {
                <span class="pg-btn__icon"><app-icon-arrow-right [size]="14" /></span>
              }
            </a>
          </article>
        }
      </div>
    }
    @if (tiers().length > 0) {
      <p class="ppg__note pg-muted">
        Downloading a redesign costs
        @for (tier of tiers(); track tier.key; let last = $last) {
          <b>{{ tier.download_credit_cost }} credits</b> for {{ tier.label }}{{ last ? '.' : ', ' }}
        }
        Each generation costs 1 credit. Previews are free, and re-downloading a tier you've paid for is free.
      </p>
    }
  `,
  styles: [
    `
      .ppg {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 40px 28px;
        align-items: center;
        padding-top: 28px;
      }
      .ppg__card {
        display: grid;
        gap: 16px;
        padding-top: 44px;
      }
      .ppg__card--featured {
        transform: scale(1.06);
        z-index: 1;
      }
      .ppg__credits {
        font: 800 1.05rem/1 var(--pg-font-heading);
      }
      .ppg__name {
        font-size: var(--pg-text-xl);
      }
      .ppg__price {
        display: flex;
        align-items: baseline;
        gap: 8px;
      }
      .ppg__price span {
        font: 800 var(--pg-text-4xl) / 1 var(--pg-font-heading);
        letter-spacing: -0.03em;
      }
      .ppg__price small {
        color: var(--pg-muted-fg);
        font-weight: 600;
      }
      .ppg__features {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        gap: 10px;
        font-size: var(--pg-text-sm);
      }
      .ppg__features li {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .ppg__tick {
        --_size: 22px;
        box-shadow: none;
      }
      .ppg__star {
        position: absolute;
        top: -40px;
        right: -22px;
        width: 92px;
        height: 92px;
        display: grid;
        place-items: center;
        align-content: center;
        gap: 2px;
        border-radius: 50%;
        background: var(--pg-amber);
        border: var(--pg-bw) solid var(--pg-fg);
        box-shadow: var(--pg-pop-active);
        outline: 2px dashed var(--pg-fg);
        outline-offset: -9px;
        transform: rotate(15deg);
        color: var(--pg-fg);
        text-align: center;
      }
      .ppg__star ::ng-deep svg {
        fill: var(--pg-card);
        stroke-width: 2;
      }
      .ppg__star span {
        font: 700 0.62rem/1.1 var(--pg-font-heading);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }
      .ppg__star b {
        font-size: 0.82rem;
        font-weight: 800;
      }
      .ppg__note {
        margin-top: 36px;
        font-size: var(--pg-text-sm);
      }
      @media (max-width: 640px) {
        .ppg__card--featured {
          transform: none;
        }
        .ppg__star {
          right: -4px;
        }
      }
    `,
  ],
})
export class PgPackGridComponent implements OnInit {
  private readonly api = inject(RedoWebsApiService);
  readonly packs = signal<CreditPack[]>([]);
  readonly tiers = signal<PublicTier[]>([]);
  readonly loading = signal(true);
  readonly error = signal(false);

  private readonly badgeColors = ['', 'pg-icon-badge--pink', 'pg-icon-badge--amber', 'pg-icon-badge--mint'];

  ngOnInit(): void {
    forkJoin({ packs: this.api.getCreditPacks(), tiers: this.api.getTiers() }).subscribe({
      next: ({ packs, tiers }) => {
        this.packs.set(packs.items);
        this.tiers.set(tiers.items);
        this.loading.set(false);
      },
      error: () => {
        this.error.set(true);
        this.loading.set(false);
      },
    });
  }

  price(pack: CreditPack): string {
    return formatUsd(pack.price_usd_cents);
  }

  features(pack: CreditPack): string[] {
    const perCredit = (pack.price_usd_cents / pack.credits / 100).toFixed(2);
    const lines = [`$${perCredit} per credit`];
    for (const tier of this.tiers()) {
      const downloads = Math.floor(pack.credits / tier.download_credit_cost);
      if (downloads > 0) {
        lines.push(`Enough for ${downloads} ${tier.label} download${downloads === 1 ? '' : 's'}`);
      }
    }
    lines.push('Pay with PayPal or card');
    return lines;
  }

  isFeatured(index: number): boolean {
    const n = this.packs().length;
    return n >= 3 && index === Math.floor(n / 2);
  }

  badgeClass(index: number): string {
    return `pg-icon-badge pg-card__float ${this.badgeColors[index % this.badgeColors.length]}`;
  }

  /** Label of the most expensive tier this pack covers on its own. */
  topTier(pack: CreditPack): string | null {
    const affordable = this.tiers()
      .filter((t) => t.download_credit_cost <= pack.credits)
      .sort((a, b) => b.download_credit_cost - a.download_credit_cost);
    return affordable[0]?.label ?? null;
  }
}
