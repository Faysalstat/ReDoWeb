import { Component, OnInit, signal } from '@angular/core';

import { CardComponent } from '../../../shared/ui/card/card.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminRevenueResponse } from '../core/admin-api.models';
import { StatTileComponent } from '../ui/stat-tile/stat-tile.component';

const RANGE_PRESETS = [7, 30, 90] as const;

/** Revenue is aggregated from the Purchase table, which already covers
 * both `source="stripe"` and `source="manual_admin"` rows -- Stripe
 * billing itself (Milestone 7) isn't built yet, so real revenue reads $0
 * here until that lands. This page is built now so it lights up
 * automatically once Stripe is wired, rather than being a later addition. */
@Component({
  selector: 'app-admin-earnings',
  standalone: true,
  imports: [CardComponent, StatTileComponent, SpinnerComponent],
  templateUrl: './admin-earnings.component.html',
})
export class AdminEarningsComponent implements OnInit {
  readonly rangePresets = RANGE_PRESETS;
  readonly selectedDays = signal<number>(30);
  readonly revenue = signal<AdminRevenueResponse | null>(null);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  constructor(private readonly api: AdminApiService) {}

  ngOnInit(): void {
    this.load();
  }

  selectRange(days: number): void {
    if (days === this.selectedDays()) return;
    this.selectedDays.set(days);
    this.load();
  }

  formatUsd(value: number): string {
    return `$${value.toFixed(2)}`;
  }

  private load(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.api.getEarnings(this.selectedDays()).subscribe({
      next: (res) => {
        this.revenue.set(res);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load earnings.');
        this.loading.set(false);
      },
    });
  }
}
