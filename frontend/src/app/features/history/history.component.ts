import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { isTerminal, stagePercent, statusBadgeVariant, statusLabel, tierLabel } from '../../core/project-status';
import { ProjectListItem } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';
import { BadgeComponent, BadgeVariant } from '../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { ProgressBarComponent } from '../../shared/ui/progress-bar/progress-bar.component';

const TIER_BADGE_VARIANT: Record<string, BadgeVariant> = {
  basic: 'muted',
  premium: 'warning',
  pro: 'accent',
};

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [RouterLink, DatePipe, AppHeaderComponent, BadgeComponent, ButtonComponent, ProgressBarComponent],
  templateUrl: './history.component.html',
  styleUrl: './history.component.css',
})
export class HistoryComponent implements OnInit {
  readonly projects = signal<ProjectListItem[]>([]);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  readonly statusLabel = statusLabel;
  readonly statusBadgeVariant = statusBadgeVariant;
  readonly stagePercent = stagePercent;
  readonly isTerminal = isTerminal;
  readonly tierLabel = tierLabel;

  constructor(private readonly api: RedoWebsApiService) {}

  tierBadgeVariant(tier: string): BadgeVariant {
    return TIER_BADGE_VARIANT[tier] ?? 'muted';
  }

  ngOnInit(): void {
    this.api.listProjects().subscribe({
      next: (projects) => {
        this.projects.set(projects);
        this.loading.set(false);
      },
      error: (err: HttpErrorResponse) => {
        const detail = err.error?.detail;
        this.errorMessage.set(typeof detail === 'string' ? detail : 'Could not load your generations.');
        this.loading.set(false);
      },
    });
  }
}
