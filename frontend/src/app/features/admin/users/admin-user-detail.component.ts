import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { BadgeComponent, BadgeVariant } from '../../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminUserDetailResponse } from '../core/admin-api.models';
import { StatTileComponent } from '../ui/stat-tile/stat-tile.component';

const TIER_BADGE_VARIANT: Record<string, BadgeVariant> = {
  basic: 'muted',
  premium: 'warning',
  pro: 'accent',
};

/** A user's wallet balance, full credit ledger, and generation history in
 * one place -- also hosts the "Issue Adjustment" refund/goodwill-credit
 * form (POST /users/{id}/adjustments), since that's the one action an
 * admin needs while looking at exactly this data. */
@Component({
  selector: 'app-admin-user-detail',
  standalone: true,
  imports: [RouterLink, DatePipe, FormsModule, StatTileComponent, SpinnerComponent, ButtonComponent, BadgeComponent],
  templateUrl: './admin-user-detail.component.html',
})
export class AdminUserDetailComponent implements OnInit {
  readonly detail = signal<AdminUserDetailResponse | null>(null);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  readonly adjustmentAmount = signal<number | null>(null);
  readonly adjustmentNote = signal('');
  readonly adjustmentSubmitting = signal(false);
  readonly adjustmentError = signal('');
  readonly adjustmentSuccess = signal('');

  private userId = '';

  constructor(
    private readonly route: ActivatedRoute,
    private readonly api: AdminApiService
  ) {}

  ngOnInit(): void {
    this.userId = this.route.snapshot.paramMap.get('id') ?? '';
    this.load();
  }

  tierBadgeVariant(tier: string | null): BadgeVariant {
    return tier ? (TIER_BADGE_VARIANT[tier] ?? 'muted') : 'muted';
  }

  submitAdjustment(): void {
    const amount = this.adjustmentAmount();
    const note = this.adjustmentNote().trim();
    this.adjustmentError.set('');
    this.adjustmentSuccess.set('');

    if (!amount) {
      this.adjustmentError.set('Amount must be a nonzero number of credits.');
      return;
    }
    if (!note) {
      this.adjustmentError.set('A note is required for every adjustment.');
      return;
    }

    this.adjustmentSubmitting.set(true);
    this.api.issueAdjustment(this.userId, { amount, note }).subscribe({
      next: () => {
        this.adjustmentSubmitting.set(false);
        this.adjustmentSuccess.set(`Adjustment applied. New balance updates below.`);
        this.adjustmentAmount.set(null);
        this.adjustmentNote.set('');
        this.load();
      },
      error: (err) => {
        this.adjustmentSubmitting.set(false);
        this.adjustmentError.set(err?.error?.detail ?? 'Failed to apply adjustment.');
      },
    });
  }

  private load(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.api.getUserDetail(this.userId).subscribe({
      next: (res) => {
        this.detail.set(res);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load user.');
        this.loading.set(false);
      },
    });
  }
}
