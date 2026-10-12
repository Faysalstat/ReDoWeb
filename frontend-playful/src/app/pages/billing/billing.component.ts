import { CurrencyPipe, DatePipe } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { PurchaseHistoryItem } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { WalletService } from '../../core/wallet.service';
import { IconArrowRight } from '../../ui/icons';

const STATUS: Record<string, { label: string; chip: string }> = {
  completed: { label: 'Paid', chip: 'pg-chip pg-chip--mint' },
  pending: { label: 'Processing', chip: 'pg-chip pg-chip--amber' },
  failed: { label: 'Failed', chip: 'pg-chip pg-chip--danger' },
  refunded: { label: 'Refunded', chip: 'pg-chip' },
};

/** /settings/billing: credit balance + real purchase history (PayPal packs
 * and any credits an admin granted), from GET /billing/purchases. */
@Component({
  selector: 'pg-billing',
  standalone: true,
  imports: [RouterLink, DatePipe, CurrencyPipe, IconArrowRight],
  template: `
    <div class="pg-wrap bl">
      <section class="pg-card bl__wallet">
        <div class="bl__coin" aria-hidden="true">
          <span>{{ wallet.balance() ?? '–' }}</span>
        </div>
        <div class="bl__copy">
          <span class="pg-kicker">Your wallet</span>
          <h1 class="bl__title">
            @if (wallet.balance() !== null) {
              {{ wallet.balance() }} credit{{ wallet.balance() === 1 ? '' : 's' }}
            } @else {
              Pay as you go
            }
          </h1>
          <p class="pg-muted">
            Each redesign costs 1 credit to start, and buying a tier's design costs that tier's price in credits.
            Previews are free, and re-downloading a tier you've paid for is free.
          </p>
          <a class="pg-btn" routerLink="/checkout">Buy credits <span class="pg-btn__icon"><app-icon-arrow-right [size]="14" /></span></a>
        </div>
      </section>

      <section class="bl__history">
        <h2 class="bl__h2">Purchase history</h2>
        <div class="pg-table-wrap">
          <table class="pg-table">
            <thead>
              <tr><th>Date</th><th>Description</th><th>Amount</th><th>Status</th></tr>
            </thead>
            <tbody>
              @if (loading()) {
                <tr><td colspan="4" class="pg-muted">Loading…</td></tr>
              } @else if (error()) {
                <tr><td colspan="4" class="pg-err">Couldn't load your purchases. Please refresh.</td></tr>
              } @else {
                @for (p of purchases(); track p.id) {
                  <tr>
                    <td>{{ p.created_at | date: 'mediumDate' }}</td>
                    <td>{{ description(p) }}</td>
                    <td><b>{{ p.amount_usd_cents / 100 | currency: 'USD' }}</b></td>
                    <td><span [class]="statusChip(p.status)">{{ statusLabel(p.status) }}</span></td>
                  </tr>
                } @empty {
                  <tr><td colspan="4" class="pg-muted">No purchases yet.</td></tr>
                }
              }
            </tbody>
          </table>
        </div>
        <p class="pg-muted bl__fine">
          Payments are processed by PayPal. A purchase showing "Processing" is waiting for PayPal to confirm it. The
          credits are added automatically once it does.
        </p>
      </section>
    </div>
  `,
  styles: [
    `
      .bl { padding-block: 48px 96px; display: grid; gap: 56px; }
      .bl__wallet { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 48px; padding: 40px; overflow: hidden; box-shadow: 8px 8px 0 var(--pg-fg); }
      .bl__coin {
        position: relative; display: grid; place-items: center; width: 200px; height: 200px; border-radius: 50%;
        background: var(--pg-amber); border: 2px solid var(--pg-fg); box-shadow: 8px 8px 0 var(--pg-fg);
      }
      .bl__coin::after { content: ''; position: absolute; inset: 16px; border-radius: 50%; border: 3px dashed var(--pg-fg); opacity: 0.35; }
      .bl__coin span { font: 800 clamp(3rem, 7vw, 4.5rem) / 1 var(--pg-font-heading); letter-spacing: -0.04em; }
      .bl__copy { display: grid; gap: 14px; justify-items: start; }
      .bl__copy p { max-width: 56ch; }
      .bl__title { font-size: clamp(2rem, 4.5vw, var(--pg-text-4xl)); }
      .bl__history { display: grid; gap: 18px; }
      .bl__h2 { font-size: var(--pg-text-2xl); }
      .bl__fine { font-size: var(--pg-text-xs); }
      @media (max-width: 720px) {
        .bl__wallet { grid-template-columns: 1fr; justify-items: start; gap: 28px; padding: 26px; box-shadow: 4px 4px 0 var(--pg-fg); }
        .bl__coin { width: 140px; height: 140px; box-shadow: 4px 4px 0 var(--pg-fg); }
      }
    `,
  ],
})
export class BillingComponent implements OnInit {
  private readonly api = inject(RedoWebsApiService);
  readonly wallet = inject(WalletService);

  readonly purchases = signal<PurchaseHistoryItem[]>([]);
  readonly loading = signal(true);
  readonly error = signal(false);

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
    return STATUS[status]?.label ?? status;
  }

  statusChip(status: string): string {
    return STATUS[status]?.chip ?? 'pg-chip';
  }

  description(item: PurchaseHistoryItem): string {
    if (item.source === 'manual_admin') return `${item.credits} credits (granted by support)`;
    if (item.source === 'mock') return `${item.credits} credits (test payment)`;
    return `${item.credits} credits`;
  }
}
