import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { BadgeComponent } from '../../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminTierRow } from '../core/admin-api.models';
import { AdminCreditPacksComponent } from '../credit-packs/admin-credit-packs.component';

interface TierDraft {
  label: string;
  sortOrder: number;
  cost: number;
}

/** Everything users pay: each tier's label, display order, on/off and
 * download cost, plus the credit packs they buy credits with (the existing
 * pack editor, embedded). The tier `key` is shown read-only -- it's used in
 * storage paths and generation history. AI models per tier stay on Model
 * config. */
@Component({
  selector: 'app-admin-tiers-pricing',
  standalone: true,
  imports: [FormsModule, BadgeComponent, ButtonComponent, SpinnerComponent, AdminCreditPacksComponent],
  templateUrl: './admin-tiers-pricing.component.html',
})
export class AdminTiersPricingComponent implements OnInit {
  readonly tiers = signal<AdminTierRow[]>([]);
  readonly drafts = signal<Record<string, TierDraft>>({});
  readonly loading = signal(true);
  readonly busyKey = signal<string | null>(null);
  readonly errorMessage = signal('');
  readonly savedMessage = signal('');

  constructor(private readonly api: AdminApiService) {}

  ngOnInit(): void {
    this.load();
  }

  draft(key: string): TierDraft {
    return this.drafts()[key];
  }

  update(key: string, field: keyof TierDraft, value: string | number): void {
    const current = this.drafts()[key];
    this.drafts.set({ ...this.drafts(), [key]: { ...current, [field]: field === 'label' ? value : Number(value) } });
  }

  /** Below 3, the 3 free signup credits can pay for a download -- which is
   * deliberately not possible (CLAUDE.md). Warn, don't block. */
  costWarning(key: string): boolean {
    const cost = this.draft(key)?.cost ?? 0;
    return cost >= 1 && cost < 3;
  }

  save(tier: AdminTierRow): void {
    const d = this.draft(tier.key);
    const label = d.label.trim();
    const cost = Math.floor(d.cost);
    if (!label || cost < 1) {
      this.errorMessage.set('Each tier needs a label and a download cost of at least 1 credit.');
      return;
    }
    this.begin(tier.key);
    this.api.updateTier(tier.key, { label, sort_order: Math.floor(d.sortOrder) || 0, download_credit_cost: cost }).subscribe({
      next: (row) => this.done(`Saved ${row.label}.`),
      error: (err) => this.failed(err, `save ${tier.label}`),
    });
  }

  toggle(tier: AdminTierRow): void {
    this.begin(tier.key);
    this.api.setTierActive(tier.key, !tier.is_active).subscribe({
      next: (row) => this.done(`${row.label} is now ${row.is_active ? 'enabled' : 'disabled'}.`),
      error: (err) => this.failed(err, `update ${tier.label}`),
    });
  }

  private begin(key: string): void {
    this.busyKey.set(key);
    this.errorMessage.set('');
    this.savedMessage.set('');
  }

  private done(message: string): void {
    this.busyKey.set(null);
    this.savedMessage.set(message);
    this.load();
  }

  private failed(err: HttpErrorResponse, action: string): void {
    this.busyKey.set(null);
    const detail = err.error?.detail;
    this.errorMessage.set(typeof detail === 'string' ? detail : `Failed to ${action}.`);
  }

  private load(): void {
    this.api.listTiers().subscribe({
      next: (res) => {
        this.tiers.set(res.items);
        const drafts: Record<string, TierDraft> = {};
        for (const t of res.items) {
          drafts[t.key] = { label: t.label, sortOrder: t.sort_order, cost: t.download_credit_cost };
        }
        this.drafts.set(drafts);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load tiers.');
        this.loading.set(false);
      },
    });
  }
}
