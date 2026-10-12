import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, OnInit, signal, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';

import { isTerminal, stagePercent, statusBadgeVariant, statusLabel, tierLabel } from '../../core/project-status';
import { ProjectListItem } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';
import { BadgeComponent, BadgeVariant } from '../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { IconAlertTriangle } from '../../shared/ui/icons/icons';
import { ProgressBarComponent } from '../../shared/ui/progress-bar/progress-bar.component';

const TIER_BADGE_VARIANT: Record<string, BadgeVariant> = {
  basic: 'muted',
  premium: 'warning',
  pro: 'accent',
};

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    AppHeaderComponent,
    BadgeComponent,
    ButtonComponent,
    ProgressBarComponent,
    IconAlertTriangle,
  ],
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

  readonly expiredProject = signal<ProjectListItem | null>(null);
  private readonly expiredDialog = viewChild.required<ElementRef<HTMLDialogElement>>('expiredDialog');

  constructor(private readonly api: RedoWebsApiService) {}

  /** The retention cleanup removed every preview and none was bought, so
   * there's nothing left to open -- the row shows a warning chip instead
   * of View. A project with a purchased design keeps View (that design is
   * never deleted). */
  isPreviewExpired(project: ProjectListItem): boolean {
    return !!project.previews_expired && project.purchased_tiers.length === 0;
  }

  openExpiredNotice(project: ProjectListItem): void {
    this.expiredProject.set(project);
    this.expiredDialog().nativeElement.showModal();
  }

  /** Clicking the backdrop (the <dialog> element itself, outside its
   * content box) closes it, like a regular modal. */
  onExpiredDialogClick(event: MouseEvent, dialog: HTMLDialogElement): void {
    if (event.target === dialog) {
      dialog.close();
    }
  }

  /** "Premium, Pro" -- only shown when more than one tier is paid for. */
  paidLabels(tiers: string[]): string {
    return tiers.map(tierLabel).join(', ');
  }

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
