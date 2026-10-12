import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { FormsModule } from '@angular/forms';

import { BadgeComponent, BadgeVariant } from '../../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminProjectDetailResponse } from '../core/admin-api.models';

const STATUS_BADGE_VARIANT: Record<string, BadgeVariant> = {
  succeeded: 'success',
  ready: 'success',
  failed: 'danger',
  rejected: 'danger',
  running: 'warning',
  generating: 'warning',
};

/** Per-project generation history -- one card per GenerationJob showing
 * which model(s) it used, which prompt template, token counts, and
 * estimated cost (via admin_analytics_service.get_token_usage_by_job,
 * the authoritative per-job source since current tier/model settings can
 * drift after a past job ran). */
@Component({
  selector: 'app-admin-project-detail',
  standalone: true,
  imports: [RouterLink, DatePipe, FormsModule, SpinnerComponent, BadgeComponent, ButtonComponent],
  templateUrl: './admin-project-detail.component.html',
  styleUrl: './admin-project-detail.component.css',
})
export class AdminProjectDetailComponent implements OnInit {
  readonly detail = signal<AdminProjectDetailResponse | null>(null);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  deleteReason = '';
  readonly deleting = signal(false);
  readonly deleteError = signal('');
  readonly deleteResult = signal('');

  constructor(
    private readonly route: ActivatedRoute,
    private readonly api: AdminApiService
  ) {}

  ngOnInit(): void {
    this.load();
  }

  /** Soft delete: every file on disk goes (purchased designs too, no
   * automatic refund), the project's history stays, and the owner no
   * longer sees it. */
  deleteProject(): void {
    const d = this.detail();
    if (!d || this.deleting()) return;
    const paid = d.paid_tiers.reduce((sum, t) => sum + t.credits, 0);
    const warning =
      d.paid_tiers.length > 0
        ? `\n\nThe owner PAID ${paid} credits for: ${d.paid_tiers.map((t) => t.tier).join(', ')}. ` +
          'Those designs will be deleted too and nothing is refunded automatically — ' +
          "use a credit adjustment on the user's page if you want to refund."
        : '';
    if (
      !confirm(
        `Delete ${d.source_url}?\n\nAll of this project's files are removed and the owner will no longer see it. ` +
          `Its history (jobs, costs, payments) is kept. This cannot be undone.${warning}`
      )
    ) {
      return;
    }
    this.deleting.set(true);
    this.deleteError.set('');
    this.api.deleteProject(d.project_id, this.deleteReason.trim() || null).subscribe({
      next: (res) => {
        this.deleting.set(false);
        this.deleteResult.set(`Deleted — freed ${(res.bytes_freed / 1024 ** 2).toFixed(1)} MB.`);
        this.load();
      },
      error: (err) => {
        this.deleting.set(false);
        this.deleteError.set(err?.error?.detail || 'Failed to delete project.');
      },
    });
  }

  private load(): void {
    const projectId = this.route.snapshot.paramMap.get('id') ?? '';
    this.loading.set(true);
    this.api.getProjectDetail(projectId).subscribe({
      next: (res) => {
        this.detail.set(res);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load project.');
        this.loading.set(false);
      },
    });
  }

  statusBadgeVariant(status: string): BadgeVariant {
    return STATUS_BADGE_VARIANT[status] ?? 'muted';
  }

  formatUsd(value: number): string {
    return `$${value.toFixed(4)}`;
  }
}
