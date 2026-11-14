import { Component, OnInit, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ArrowRight, Check, LucideAngularModule } from 'lucide-angular';
import { forkJoin } from 'rxjs';

import { CreditPack, PublicTier } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { RevealDirective } from '../motion/reveal.directive';
import { formatUsd } from '../design/format';

/** Tiers that get the SEO agent after purchase. Mirrors the backend's
 * hardcoded `seo_agent.SEO_TIER_KEYS`; the public GET /tiers doesn't expose
 * it (the project page reads `tier_actions[tier].seo_available` instead). */
const SEO_TIER_KEYS = new Set(['pro', 'premium']);

type Accent = { card: string; label: string; price: string; button: string };

/** Card colours in display order: free card, then each paid tier. */
const ACCENTS: Accent[] = [
  {
    card: 'border-green-500/40 bg-green-500/[0.04]',
    label: 'text-muted-foreground',
    price: 'text-green-400',
    button: 'border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10',
  },
  {
    card: 'border-cyan-500/50 bg-cyan-500/[0.05] shadow-xl shadow-cyan-500/5',
    label: 'text-muted-foreground',
    price: 'text-cyan-400',
    button: 'border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10',
  },
  {
    card: 'border-purple-500/50 bg-purple-500/[0.06] shadow-xl shadow-purple-500/5',
    label: 'text-muted-foreground',
    price: 'text-purple-400',
    button: 'border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10',
  },
  {
    card: 'border-primary/50 bg-primary/[0.06]',
    label: 'text-muted-foreground',
    price: 'text-primary',
    button: 'border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10',
  },
];

const RECOMMENDED_BUTTON = 'bg-orange-500 hover:bg-orange-500/90 text-white shadow-lg shadow-orange-500/25';

interface TierCard {
  tier: PublicTier;
  /** Smallest credit pack that covers this tier's download cost, if any. */
  pack: CreditPack | null;
  accent: Accent;
  recommended: boolean;
  features: string[];
}

/** Pricing cards: a free-preview card plus one card per active tier, priced
 * by the smallest admin-configured credit pack that covers the tier's
 * download cost (public GET /billing/credit-packs + GET /tiers). Shared by
 * the home page and /pricing. */
@Component({
  selector: 'app-credit-pack-grid',
  standalone: true,
  imports: [RouterLink, LucideAngularModule, RevealDirective],
  host: { class: 'block' },
  template: `
    <div class="relative">
      <!-- Floating redesign thumbnails behind the cards (wide screens only, so they never cause horizontal scroll). -->
      <div class="hidden xl:block absolute -inset-x-28 -inset-y-20 pointer-events-none select-none" aria-hidden="true">
        @for (t of thumbs; track t.src) {
          <img
            [src]="t.src"
            alt=""
            loading="lazy"
            class="absolute w-44 rounded-lg border border-white/10 shadow-2xl opacity-[0.18] blur-[1px]"
            [style.top]="t.top"
            [style.left]="t.left"
            [style.right]="t.right"
            [style.transform]="'rotate(' + t.rotate + 'deg)'"
          />
        }
      </div>

      @if (loading()) {
        <div class="relative grid sm:grid-cols-2 lg:grid-cols-3 gap-8">
          @for (i of [0, 1, 2]; track i) {
            <div class="h-[26rem] rounded-2xl border border-border/50 bg-card/50 animate-pulse"></div>
          }
        </div>
      } @else if (error()) {
        <p class="relative text-center text-muted-foreground">Prices couldn't be loaded right now. Please try again shortly.</p>
      } @else {
        <div class="relative grid sm:grid-cols-2 lg:grid-cols-3 gap-8 text-left">
          <!-- Free preview -->
          <div reveal class="relative rounded-2xl border p-8 flex flex-col backdrop-blur-sm" [class]="accents[0].card">
            <p class="text-xs font-semibold uppercase tracking-wider mb-2" [class]="accents[0].label">Free preview</p>
            <p class="font-display text-5xl font-bold mb-3" [class]="accents[0].price">$0</p>
            <p class="text-sm text-muted-foreground mb-8">Browse your AI redesign for free</p>
            <ul class="space-y-3 mb-10">
              @for (f of freeFeatures; track f) {
                <li class="flex items-start gap-3 text-sm">
                  <lucide-icon [img]="Check" class="w-4 h-4 mt-0.5 shrink-0 text-green-400" /><span>{{ f }}</span>
                </li>
              }
            </ul>
            <a
              routerLink="/"
              class="mt-auto inline-flex h-11 items-center justify-center gap-2 rounded-lg text-sm font-semibold transition-colors"
              [class]="accents[0].button"
            >
              Start Redesign <lucide-icon [img]="ArrowRight" class="w-4 h-4" />
            </a>
          </div>

          @for (c of cards(); track c.tier.key; let i = $index) {
            <div
              reveal
              [revealDelay]="(i + 1) * 100"
              class="relative rounded-2xl border p-8 flex flex-col backdrop-blur-sm"
              [class]="c.accent.card"
            >
              @if (c.recommended) {
                <span
                  class="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-orange-500 px-3 py-0.5 text-xs font-semibold text-white whitespace-nowrap"
                  >Recommended</span
                >
              }
              <p class="text-xs font-semibold uppercase tracking-wider mb-2" [class]="c.accent.label">
                {{ c.tier.label }} redesign
              </p>
              <p class="font-display text-5xl font-bold mb-3" [class]="c.accent.price">
                {{ c.pack ? price(c.pack) : c.tier.download_credit_cost + ' credits' }}
              </p>
              <p class="text-sm text-muted-foreground mb-8">
                {{ c.tier.download_credit_cost }} credits · one-time, no subscription
              </p>
              <ul class="space-y-3 mb-10">
                @for (f of c.features; track f) {
                  <li class="flex items-start gap-3 text-sm">
                    <lucide-icon [img]="Check" class="w-4 h-4 mt-0.5 shrink-0 text-green-400" /><span>{{ f }}</span>
                  </li>
                }
              </ul>
              <a
                routerLink="/checkout"
                [queryParams]="c.pack ? { pack: c.pack.id } : {}"
                class="mt-auto inline-flex h-11 items-center justify-center gap-2 rounded-lg text-sm font-semibold transition-colors"
                [class]="c.recommended ? recommendedButton : c.accent.button"
              >
                Get Started <lucide-icon [img]="ArrowRight" class="w-4 h-4" />
              </a>
            </div>
          }
        </div>
      }
    </div>

    @if (!loading() && !error() && packs().length > 0) {
      <p class="relative text-sm text-muted-foreground mt-10 text-center">
        Credit packs:
        @for (pack of packs(); track pack.id; let last = $last) {
          <a routerLink="/checkout" [queryParams]="{ pack: pack.id }" class="text-foreground hover:text-primary"
            >{{ pack.credits }} credits <span class="text-green-400 font-semibold">{{ price(pack) }}</span></a
          >{{ last ? '' : ' · ' }}
        }
        — each generation costs 1 credit, and re-downloading a design you bought is free.
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
  protected readonly ArrowRight = ArrowRight;
  protected readonly accents = ACCENTS;
  protected readonly recommendedButton = RECOMMENDED_BUTTON;

  protected readonly freeFeatures = [
    'Live interactive preview',
    'Your home page redesigned by AI',
    'No credit card needed',
    'No downloads',
  ];

  protected readonly thumbs = [
    { src: '/assets/images/template-showcase/saas-tech.jpg', top: '-2%', left: '0%', rotate: -6 },
    { src: '/assets/images/template-showcase/creative-agency.jpg', top: '42%', left: '-2%', rotate: 4 },
    { src: '/assets/images/floating-bg/business-solutions-woman.jpg', top: '78%', left: '3%', rotate: -3 },
    { src: '/assets/images/template-showcase/corporate-solutions.jpg', top: '0%', right: '0%', rotate: 5 },
    { src: '/assets/images/template-showcase/modern-ecommerce.jpg', top: '38%', right: '-3%', rotate: -4 },
    { src: '/assets/images/floating-bg/mixed-corporate-woman.jpg', top: '74%', right: '2%', rotate: 3 },
  ] as { src: string; top: string; left?: string; right?: string; rotate: number }[];

  /** One card per active tier (GET /tiers is already ordered); the first paid
   * tier is the recommended one. */
  readonly cards = computed<TierCard[]>(() => {
    const packs = [...this.packs()].sort((a, b) => a.credits - b.credits);
    return this.tiers().map((tier, i) => ({
      tier,
      pack: packs.find((p) => p.credits >= tier.download_credit_cost) ?? null,
      accent: ACCENTS[Math.min(i + 1, ACCENTS.length - 1)],
      recommended: i === 0 && this.tiers().length > 1,
      features: this.features(tier),
    }));
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

  private features(tier: PublicTier): string[] {
    const lines = ['Full redesigned website (ZIP)', 'All pages generated'];
    if (SEO_TIER_KEYS.has(tier.key)) {
      lines.push('SEO agent pass included');
    }
    lines.push('Free re-downloads', 'Pay with PayPal or card');
    return lines;
  }
}
