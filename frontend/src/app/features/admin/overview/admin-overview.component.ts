import { Component, OnInit, signal } from '@angular/core';

import { CardComponent } from '../../../shared/ui/card/card.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminOverviewResponse } from '../core/admin-api.models';
import { StatTileComponent } from '../ui/stat-tile/stat-tile.component';

const RANGE_PRESETS = [7, 30, 90] as const;

/** The first admin page, deliberately built and proven end-to-end before
 * any other admin page or chart component -- see docs/PROGRESS.md's
 * Milestone 11 build order. */
@Component({
  selector: 'app-admin-overview',
  standalone: true,
  imports: [CardComponent, StatTileComponent, SpinnerComponent],
  templateUrl: './admin-overview.component.html',
})
export class AdminOverviewComponent implements OnInit {
  readonly rangePresets = RANGE_PRESETS;
  readonly selectedDays = signal<number>(30);
  readonly stats = signal<AdminOverviewResponse | null>(null);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  constructor(private readonly api: AdminApiService) {}

  ngOnInit(): void {
    this.load();
  }

  selectRange(days: number): void {
    if (days === this.selectedDays()) {
      return;
    }
    this.selectedDays.set(days);
    this.load();
  }

  formatUsd(value: number): string {
    return `$${value.toFixed(2)}`;
  }

  private load(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.api.getOverview(this.selectedDays()).subscribe({
      next: (res) => {
        this.stats.set(res);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load overview data.');
        this.loading.set(false);
      },
    });
  }
}
