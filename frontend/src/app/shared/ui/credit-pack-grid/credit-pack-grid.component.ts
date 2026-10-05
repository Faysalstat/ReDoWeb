import { Component, OnInit, computed, signal } from '@angular/core';
import { forkJoin } from 'rxjs';

import { CreditPack, PublicTier } from '../../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../../core/redowebs-api.service';
import { PricingTierComponent } from '../pricing-tier/pricing-tier.component';

export function formatUsd(cents: number): string {
  return cents % 100 === 0 ? `$${cents / 100}` : `$${(cents / 100).toFixed(2)}`;
}

/** Real, admin-configured credit packs plus each tier's download cost, from
 * the public GET /billing/credit-packs and GET /tiers endpoints. Shared by
 * the home page's pricing section and the /pricing page. */
@Component({
  selector: 'app-credit-pack-grid',
  standalone: true,
  imports: [PricingTierComponent],
  template: `
    @if (loading()) {
      <p class="text-muted">Loading prices…</p>
    } @else if (error()) {
      <p class="text-muted">Prices couldn't be loaded right now. Please try again shortly.</p>
    } @else if (packs().length === 0) {
      <p class="text-muted">Credit packs aren't on sale yet — check back soon. Previews are always free.</p>
    } @else {
      <div class="grid-3" style="align-items: start">
        @for (pack of packs(); track pack.id) {
          <app-pricing-tier
            [name]="pack.name"
            [price]="price(pack)"
            period="one-time"
            [tagline]="pack.credits + ' credits'"
            [features]="features(pack)"
            [highlighted]="pack.id === bestValueId()"
            ctaLabel="Buy credits"
            ctaLink="/checkout"
            [ctaQueryParams]="{ pack: pack.id }"
          />
        }
      </div>
    }
    @if (tiers().length > 0) {
      <p class="text-muted" style="margin-top: var(--space-4); font-size: 13px">
        Downloading a redesign costs
        @for (tier of tiers(); track tier.key; let last = $last) {
          <b>{{ tier.download_credit_cost }} credits</b> for {{ tier.label }}{{ last ? '.' : ', ' }}
        }
        Each generation costs 1 credit; previews are free, and re-downloading a tier you've paid for is free.
      </p>
    }
  `,
})
export class CreditPackGridComponent implements OnInit {
  readonly packs = signal<CreditPack[]>([]);
  readonly tiers = signal<PublicTier[]>([]);
  readonly loading = signal(true);
  readonly error = signal(false);

  /** Highlight the cheapest-per-credit pack, but only when there's an
   * actual choice to make. */
  readonly bestValueId = computed(() => {
    const packs = this.packs();
    if (packs.length < 2) {
      return null;
    }
    return packs.reduce((best, p) =>
      p.price_usd_cents / p.credits < best.price_usd_cents / best.credits ? p : best
    ).id;
  });

  constructor(private readonly api: RedoWebsApiService) {}

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
}
