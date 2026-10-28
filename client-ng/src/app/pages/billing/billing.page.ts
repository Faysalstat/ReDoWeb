import { CurrencyPipe, DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Coins, LucideAngularModule, Receipt } from 'lucide-angular';

import { PurchaseHistoryItem } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { WalletService } from '../../core/wallet.service';
import { UiButton } from '../../shared/ui/button.directive';
import { UI_CARD } from '../../shared/ui/primitives';

const STATUS_LABELS: Record<string, string> = {
  completed: 'Paid',
  pending: 'Processing',
  failed: 'Failed',
  refunded: 'Refunded',
};

const STATUS_PILLS: Record<string, string> = {
  completed: 'bg-green-500/10 text-green-400 border-green-500/20',
  pending: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  failed: 'bg-red-500/10 text-red-400 border-red-500/20',
  refunded: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
};

/** /settings/billing: credit balance + real purchase history (PayPal packs
 * and any credits an admin granted), from GET /billing/purchases. Logic
 * copied from frontend/'s BillingSettingsComponent. */
@Component({
  selector: 'app-billing-page',
  standalone: true,
  imports: [RouterLink, DatePipe, CurrencyPipe, LucideAngularModule, UiButton, ...UI_CARD],
  template: `
    <section class="py-10 sm:py-14 px-4">
    <div class="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 class="font-display text-2xl font-bold mb-1">Billing</h1>
        <p class="text-sm text-muted-foreground">Your credit balance and every purchase.</p>
      </div>

      <div uiCard class="bg-gradient-to-r from-primary/10 to-purple-500/5 border-primary/20">
        <div uiCardContent class="p-6 flex flex-col sm:flex-row sm:items-center gap-6">
          <div class="flex items-center gap-4 flex-1">
            <div class="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
              <lucide-icon [img]="icons.Coins" class="w-6 h-6 text-primary" />
            </div>
            <div>
              <p class="text-xs text-muted-foreground">Credits</p>
              <p class="font-display text-3xl font-bold">
                @if (wallet.balance() !== null) {
                  {{ wallet.balance() }} credit{{ wallet.balance() === 1 ? '' : 's' }}
                } @else {
                  Pay-as-you-go
                }
              </p>
              <p class="text-sm text-muted-foreground mt-1 max-w-xl">
                Each generation costs 1 credit and downloading a tier costs that tier's price in credits. Previews are free;
                re-downloading a tier you've paid for is free.
              </p>
            </div>
          </div>
          <a uiButton routerLink="/checkout" class="rounded-xl h-11 px-6 text-white bg-gradient-to-r from-primary to-purple-500 hover:from-primary/90 hover:to-purple-500/90">
            Buy credits
          </a>
        </div>
      </div>

      <div uiCard class="bg-card/50 border-border/50">
        <div uiCardHeader class="flex-row items-center gap-2 space-y-0">
          <lucide-icon [img]="icons.Receipt" class="w-4 h-4 text-primary" />
          <h2 uiCardTitle class="text-base font-display">Purchase history</h2>
        </div>
        <div uiCardContent class="overflow-x-auto">
          <table class="w-full text-sm min-w-[520px]">
            <thead>
              <tr class="text-left text-xs uppercase tracking-wider text-muted-foreground border-b border-border/50">
                <th class="py-3 pr-4 font-semibold">Date</th>
                <th class="py-3 pr-4 font-semibold">Description</th>
                <th class="py-3 pr-4 font-semibold">Amount</th>
                <th class="py-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              @if (loading()) {
                <tr><td colspan="4" class="py-6 text-muted-foreground">Loading…</td></tr>
              } @else if (error()) {
                <tr><td colspan="4" class="py-6 text-destructive">Couldn't load your purchases. Please refresh.</td></tr>
              } @else {
                @for (p of purchases(); track p.id) {
                  <tr class="border-b border-border/20 last:border-0 hover:bg-muted/30 transition-colors">
                    <td class="py-3 pr-4 whitespace-nowrap">{{ p.created_at | date: 'mediumDate' }}</td>
                    <td class="py-3 pr-4">{{ description(p) }}</td>
                    <td class="py-3 pr-4 tabular-nums">{{ p.amount_usd_cents / 100 | currency: 'USD' }}</td>
                    <td class="py-3">
                      <span class="text-xs px-2 py-0.5 rounded-full border font-medium" [class]="pill(p.status)">{{ statusLabel(p.status) }}</span>
                    </td>
                  </tr>
                } @empty {
                  <tr><td colspan="4" class="py-6 text-muted-foreground">No purchases yet.</td></tr>
                }
              }
            </tbody>
          </table>
        </div>
      </div>

      <p class="text-xs text-muted-foreground">
        Payments are processed by PayPal. A purchase showing "Processing" is waiting for PayPal to confirm it — the credits
        are added automatically once it does.
      </p>
    </div>
    </section>
  `,
})
export default class BillingPage implements OnInit {
  readonly purchases = signal<PurchaseHistoryItem[]>([]);
  readonly loading = signal(true);
  readonly error = signal(false);
  protected readonly icons = { Coins, Receipt };

  constructor(
    private readonly api: RedoWebsApiService,
    readonly wallet: WalletService,
  ) {}

  ngOnInit(): void {
    this.wallet.refresh();
    this.api.listPurchases().subscribe({
      next: (res) => {
        this.purchases.set(res.items);
        this.loading.set(false);
      },
      error: () => {
        this.error.set(true);
        this.loading.set(false);
      },
    });
  }

  statusLabel(status: string): string {
    return STATUS_LABELS[status] ?? status;
  }

  pill(status: string): string {
    return STATUS_PILLS[status] ?? STATUS_PILLS['pending'];
  }

  description(item: PurchaseHistoryItem): string {
    if (item.source === 'manual_admin') return `${item.credits} credits (granted by support)`;
    if (item.source === 'mock') return `${item.credits} credits (test payment)`;
    return `${item.credits} credits`;
  }
}
