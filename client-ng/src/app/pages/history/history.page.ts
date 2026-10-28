import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, OnInit, computed, signal, viewChild } from '@angular/core';
import { RouterLink } from '@angular/router';
import {
  AlertTriangle,
  ArrowRight,
  Download,
  FolderOpen,
  Loader2,
  LucideAngularModule,
  Plus,
  ShoppingBag,
  Sparkles,
} from 'lucide-angular';

import { isTerminal, stagePercent, tierLabel } from '../../core/project-status';
import { ProjectListItem } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { StatusPillComponent } from '../../shared/components/status-pill.component';
import { RevealDirective } from '../../shared/motion/reveal.directive';
import { UiButton } from '../../shared/ui/button.directive';
import { UI_CARD } from '../../shared/ui/primitives';

/** /history: every project the user submitted, newest first. Logic copied
 * from frontend/'s HistoryComponent (preview-expired chip + native <dialog>,
 * free re-download links for purchased tiers). */
@Component({
  selector: 'app-history-page',
  standalone: true,
  imports: [RouterLink, DatePipe, LucideAngularModule, RevealDirective, StatusPillComponent, UiButton, ...UI_CARD],
  templateUrl: './history.page.html',
})
export default class HistoryPage implements OnInit {
  readonly projects = signal<ProjectListItem[]>([]);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  readonly stagePercent = stagePercent;
  readonly isTerminal = isTerminal;
  readonly tierLabel = tierLabel;
  protected readonly icons = { AlertTriangle, ArrowRight, Download, Loader2, Plus, Sparkles };

  readonly stats = computed(() => {
    const projects = this.projects();
    return [
      { label: 'Total Projects', value: projects.length, icon: FolderOpen },
      { label: 'Completed', value: projects.filter((p) => p.status === 'ready').length, icon: Download },
      { label: 'Purchases', value: projects.reduce((n, p) => n + p.purchased_tiers.length, 0), icon: ShoppingBag },
    ];
  });

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
