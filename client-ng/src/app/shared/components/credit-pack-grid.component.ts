import { Component, OnInit, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Check, LucideAngularModule, Sparkles } from 'lucide-angular';
import { forkJoin } from 'rxjs';

import { CreditPack, PublicTier } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { RevealDirective } from '../motion/reveal.directive';
import { UiButton } from '../ui/button.directive';
import { formatUsd } from '../design/format';

/** Real, admin-configured credit packs plus each tier's download cost, from
 * the public GET /billing/credit-packs and GET /tiers (same data and logic as
 * frontend/'s CreditPackGridComponent), drawn as blueprint §7.5 pricing-page
 * cards. Shared by the home page and /pricing. */
@Component({
  selector: 'app-credit-pack-grid',
  standalone: true,
  imports: [RouterLink, LucideAngularModule, RevealDirective, UiButton],
  host: { class: 'block' },
  template: `
    @if (loading()) {
      <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-8">
        @for (i of [0, 1, 2]; track i) {
          <div class="h-80 rounded-2xl border border-border/50 bg-card/50 animate-pulse"></div>
        }
      </div>
    } @else if (error()) {
      <p class="text-center text-muted-foreground">Prices couldn't be loaded right now. Please try again shortly.</p>
    } @else if (packs().length === 0) {
      <p class="text-center text-muted-foreground">
        Credit packs aren't on sale yet — check back soon. Previews are always free.
      </p>
    } @else {
      <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-8 items-start text-left">
        @for (pack of packs(); track pack.id; let i = $index) {
          @let featured = pack.id === bestValueId();
          <div
            reveal
            [revealDelay]="i * 100"
            class="relative rounded-2xl border p-6 sm:p-8 flex flex-col"
            [class]="
              featured
                ? 'border-primary/40 bg-gradient-to-b from-primary/5 to-card shadow-xl shadow-primary/10'
                : 'border-border/50 bg-card/50'
            "
          >
            @if (featured) {
              <span
                class="absolute -top-3 left-1/2 -translate-x-1/2 inline-flex items-center gap-1 rounded-md px-2.5 py-0.5 text-xs font-semibold bg-gradient-to-r from-primary to-purple-500 text-white"
              >
                <lucide-icon [img]="Sparkles" class="w-3 h-3" /> Best value
              </span>
            }
            <p class="text-xs text-muted-foreground mb-2 font-semibold uppercase tracking-wider">{{ pack.name }}</p>
            <div class="flex items-end gap-2 mb-1">
              <span class="font-display text-4xl font-bold">{{ price(pack) }}</span>
              <span class="text-muted-foreground mb-1">one-time</span>
            </div>
            <p class="text-sm text-muted-foreground mb-6">{{ pack.credits }} credits</p>
            <a
              uiButton
              routerLink="/checkout"
              [queryParams]="{ pack: pack.id }"
              class="w-full rounded-xl mb-6"
              [class]="
                featured
                  ? 'bg-gradient-to-r from-primary to-purple-500 hover:from-primary/90 hover:to-purple-500/90 shadow-lg shadow-primary/25 text-white'
                  : 'bg-secondary hover:bg-secondary/80 text-foreground'
              "
              >Buy credits</a
            >
            <ul class="space-y-3">
              @for (f of features(pack); track f) {
                <li class="flex items-start gap-3 text-sm">
                  <lucide-icon [img]="Check" class="w-4 h-4 mt-0.5 text-primary" /><span>{{ f }}</span>
                </li>
              }
            </ul>
          </div>
        }
      </div>
    }
    @if (tiers().length > 0) {
      <p class="text-sm text-muted-foreground mt-8 text-center">
        Downloading a redesign costs
        @for (tier of tiers(); track tier.key; let last = $last) {
          <b class="text-foreground">{{ tier.download_credit_cost }} credits</b> for {{ tier.label }}{{ last ? '.' : ', ' }}
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

  protected readonly Check = Check;
  protected readonly Sparkles = Sparkles;

  /** Highlight the cheapest-per-credit pack, but only when there's an
   * actual choice to make. */
  readonly bestValueId = computed(() => {
    const packs = this.packs();
    if (packs.length < 2) {
      return null;
    }
    const best = packs.reduce((b, p) => (p.price_usd_cents / p.credits < b.price_usd_cents / b.credits ? p : b));
    // Equal per-credit prices (one pack = one download) have no best value.
    const tie = packs.every((p) => p.price_usd_cents / p.credits === best.price_usd_cents / best.credits);
    return tie ? null : best.id;
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
