import { CurrencyPipe, DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { PurchaseHistoryItem } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { WalletService } from '../../core/wallet.service';
import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';

const STATUS_LABELS: Record<string, string> = {
  completed: 'Paid',
  pending: 'Processing',
  failed: 'Failed',
  refunded: 'Refunded',
};

/** Credit balance + real purchase history (PayPal packs and any credits an
 * admin granted), from GET /billing/purchases. */
@Component({
  selector: 'app-billing-settings',
  standalone: true,
  imports: [RouterLink, DatePipe, CurrencyPipe, AppHeaderComponent],
  templateUrl: './billing-settings.component.html',
  styleUrl: './billing-settings.component.css',
})
export class BillingSettingsComponent implements OnInit {
  readonly purchases = signal<PurchaseHistoryItem[]>([]);
  readonly loading = signal(true);
  readonly error = signal(false);

  constructor(
    private readonly api: RedoWebsApiService,
    readonly wallet: WalletService
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

  description(item: PurchaseHistoryItem): string {
    if (item.source === 'manual_admin') return `${item.credits} credits (granted by support)`;
    if (item.source === 'mock') return `${item.credits} credits (test payment)`;
    return `${item.credits} credits`;
  }
}
