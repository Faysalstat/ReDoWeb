import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { BadgeComponent, BadgeVariant } from '../../../shared/ui/badge/badge.component';
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
  imports: [RouterLink, DatePipe, SpinnerComponent, BadgeComponent],
  templateUrl: './admin-project-detail.component.html',
  styleUrl: './admin-project-detail.component.css',
})
export class AdminProjectDetailComponent implements OnInit {
  readonly detail = signal<AdminProjectDetailResponse | null>(null);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  constructor(
    private readonly route: ActivatedRoute,
    private readonly api: AdminApiService
  ) {}

  ngOnInit(): void {
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
