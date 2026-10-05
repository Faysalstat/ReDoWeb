import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { BadgeComponent, BadgeVariant } from '../../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import {
  AdminPaymentsStatusResponse,
  AdminPurchaseDetailResponse,
  AdminPurchaseRow,
} from '../core/admin-api.models';

const PAGE_SIZE = 25;

const STATUS_BADGE: Record<string, BadgeVariant> = {
  completed: 'success',
  pending: 'warning',
  failed: 'danger',
  refunded: 'muted',
};

const MODE_LABEL: Record<string, string> = {
  mock: 'Test mode — payments are simulated, no money moves',
  paypal_sandbox: 'PayPal sandbox — test money only',
  paypal_live: 'PayPal live — real payments',
};

/** All purchases, the payment-mode banner, and the per-purchase admin
 * actions (Re-check with PayPal, Take back credits, Mark as failed). None of
 * these send or refund money -- refunds are made in the PayPal dashboard.
 * See docs/admin-payments-plan.md. */
@Component({
  selector: 'app-admin-payments',
  standalone: true,
  imports: [FormsModule, DatePipe, RouterLink, BadgeComponent, ButtonComponent, SpinnerComponent],
  templateUrl: './admin-payments.component.html',
  styleUrl: './admin-payments.component.css',
})
export class AdminPaymentsComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);

  readonly statusFilters = ['', 'pending', 'completed', 'failed', 'refunded'];
  readonly sourceFilters = ['', 'paypal', 'manual_admin', 'mock'];
  readonly modeLabel = MODE_LABEL;

  readonly paymentsStatus = signal<AdminPaymentsStatusResponse | null>(null);
  readonly rows = signal<AdminPurchaseRow[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  status = this.route.snapshot.queryParamMap.get('status') ?? '';
  source = '';
  // Deep links from a user's page pre-fill the buyer (and show their test
  // purchases too, since on one user there's nothing to hide).
  email = this.route.snapshot.queryParamMap.get('email') ?? '';
  includeMock = this.route.snapshot.queryParamMap.get('mock') === '1';

  readonly selected = signal<AdminPurchaseDetailResponse | null>(null);
  readonly detailLoading = signal(false);
  readonly actionBusy = signal(false);
  readonly actionMessage = signal('');
  readonly actionError = signal('');
  actionNote = '';

  constructor(private readonly api: AdminApiService) {}

  ngOnInit(): void {
    this.api.getPaymentsStatus().subscribe({ next: (s) => this.paymentsStatus.set(s), error: () => {} });
    this.load();
  }

  badge(status: string): BadgeVariant {
    return STATUS_BADGE[status] ?? 'muted';
  }

  sourceLabel(source: string): string {
    return source === 'manual_admin' ? 'manual' : source === 'mock' ? 'test' : source;
  }

  usd(cents: number): string {
    return `$${(cents / 100).toFixed(2)}`;
  }

  get pageCount(): number {
    return Math.max(1, Math.ceil(this.total() / PAGE_SIZE));
  }

  applyFilters(): void {
    this.page.set(1);
    this.load();
  }

  goToPage(page: number): void {
    this.page.set(page);
    this.load();
  }

  open(row: AdminPurchaseRow): void {
    this.actionMessage.set('');
    this.actionError.set('');
    this.actionNote = '';
    this.loadDetail(row.id);
  }

  close(): void {
    this.selected.set(null);
  }

  recheck(id: string): void {
    this.act(() => this.api.recheckPurchase(id), (res) =>
      `PayPal says: ${res.status}${res.reason ? ' — ' + res.reason : ''}${res.credits_granted ? ` (${res.credits_granted} credits on account)` : ''}`
    );
  }

  takeBack(id: string): void {
    if (!this.actionNote.trim()) {
      this.actionError.set('Add a note explaining the take-back.');
      return;
    }
    this.act(() => this.api.takeBackCredits(id, this.actionNote), (res) => {
      if (res.already_done) return `Already done earlier: ${res.taken_back} credits were taken back.`;
      if (res.taken_back === 0) return 'The user has 0 credits, so nothing was taken back. You can try again after they top up.';
      if (res.taken_back < res.requested)
        return `Took back ${res.taken_back} of ${res.requested} credits (the user had spent the rest). Use a manual adjustment on the user page if more needs taking back later.`;
      return `Took back ${res.taken_back} credits. Their balance is now ${res.balance_after}.`;
    });
  }

  markFailed(id: string): void {
    if (!this.actionNote.trim()) {
      this.actionError.set('Add a note explaining why this purchase is being closed.');
      return;
    }
    this.act(() => this.api.markPurchaseFailed(id, this.actionNote), (res) =>
      res.marked_failed
        ? 'Marked as failed. No money moved.'
        : `Not marked failed — PayPal shows this order as ${res.status}${res.reason ? ' (' + res.reason + ')' : ''}. ${res.status === 'completed' ? 'The credits have been added.' : ''}`
    );
  }

  private act<T>(call: () => Observable<T>, describe: (res: T) => string): void {
    const id = this.selected()?.purchase.id;
    if (!id) return;
    this.actionBusy.set(true);
    this.actionMessage.set('');
    this.actionError.set('');
    call().subscribe({
      next: (res) => {
        this.actionBusy.set(false);
        this.actionNote = '';
        this.actionMessage.set(describe(res));
        this.loadDetail(id);
        this.load();
      },
      error: (err: HttpErrorResponse) => {
        this.actionBusy.set(false);
        const detail = err.error?.detail;
        this.actionError.set(typeof detail === 'string' ? detail : 'That action failed. Please try again.');
      },
    });
  }

  private loadDetail(id: string): void {
    this.detailLoading.set(true);
    this.api.getPurchase(id).subscribe({
      next: (detail) => {
        this.selected.set(detail);
        this.detailLoading.set(false);
      },
      error: () => {
        this.detailLoading.set(false);
        this.actionError.set('Failed to load this purchase.');
      },
    });
  }

  private load(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.api
      .listPurchases({
        status: this.status || undefined,
        source: this.source || undefined,
        email: this.email.trim() || undefined,
        includeMock: this.includeMock,
        page: this.page(),
        pageSize: PAGE_SIZE,
      })
      .subscribe({
        next: (res) => {
          this.rows.set(res.items);
          this.total.set(res.total);
          this.loading.set(false);
        },
        error: () => {
          this.errorMessage.set('Failed to load purchases.');
          this.loading.set(false);
        },
      });
  }
}
