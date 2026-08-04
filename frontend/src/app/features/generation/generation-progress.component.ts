import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription, switchMap, takeWhile, timer } from 'rxjs';

import { API_BASE_URL } from '../../core/api-config';
import { STAGE_ORDER, Stage, TERMINAL_STATUSES, stageOf } from '../../core/project-status';
import { ProjectStatusResponse } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';
import { BadgeComponent } from '../../shared/ui/badge/badge.component';
import { BrowserFrameComponent } from '../../shared/ui/browser-frame/browser-frame.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { CardComponent } from '../../shared/ui/card/card.component';
import { IconAlertTriangle, IconCheck, IconExternalLink, IconMaximize2, IconX } from '../../shared/ui/icons/icons';
import { ProgressBarComponent } from '../../shared/ui/progress-bar/progress-bar.component';
import { StepItemComponent, StepStatus } from '../../shared/ui/step-item/step-item.component';

const POLL_INTERVAL_MS = 3000;
const SUBSTEP_INTERVAL_MS = 2400;

const SUBSTEPS: Partial<Record<Stage, string[]>> = {
  crawling: [
    'Fetching your homepage…',
    'Following navigation links…',
    'Checking robots.txt…',
    'Downloading images and fonts…',
  ],
  extracting: [
    'Reading page content…',
    'Identifying your logo and colors…',
    'Detecting fonts and tone of voice…',
    'Writing your brand blueprint…',
  ],
  generating: [
    'Sketching the new layout…',
    'Writing HTML and CSS…',
    'Wiring up navigation…',
    'Polishing typography and spacing…',
    'Double-checking accessibility…',
  ],
};

/** The blueprint's "Progress page" (§6a): live status for a single project,
 * reached either right after submitting from the hero or by deep link from
 * a History row. Owns the 3s status poll -- moved here from HomeComponent so
 * a page refresh mid-generation can resume by re-fetching from the URL's
 * project id instead of losing the subscription. */
@Component({
  selector: 'app-generation-progress',
  standalone: true,
  imports: [
    RouterLink,
    AppHeaderComponent,
    BadgeComponent,
    ButtonComponent,
    CardComponent,
    ProgressBarComponent,
    StepItemComponent,
    BrowserFrameComponent,
    IconAlertTriangle,
    IconCheck,
    IconMaximize2,
    IconExternalLink,
    IconX,
  ],
  templateUrl: './generation-progress.component.html',
})
export class GenerationProgressComponent implements OnInit, OnDestroy {
  readonly stage = signal<Stage>('crawling');
  readonly errorMessage = signal('');
  readonly status = signal<ProjectStatusResponse | null>(null);
  readonly previewUrl = signal('');
  readonly elapsedSeconds = signal(0);
  readonly subStatus = signal('');
  readonly isFullscreenPreview = signal(false);

  private pollSubscription?: Subscription;
  private tickSubscription?: Subscription;
  private substepSubscription?: Subscription;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly api: RedoWebsApiService,
    private readonly sanitizer: DomSanitizer
  ) {}

  get isBusy(): boolean {
    return STAGE_ORDER.includes(this.stage());
  }

  get progressPercent(): number {
    const idx = STAGE_ORDER.indexOf(this.stage());
    if (idx < 0) {
      return 0;
    }
    return Math.round(((idx + 1) / STAGE_ORDER.length) * 100);
  }

  get formattedElapsed(): string {
    const total = this.elapsedSeconds();
    const minutes = Math.floor(total / 60);
    const seconds = total % 60;
    return minutes > 0 ? `${minutes}:${seconds.toString().padStart(2, '0')}` : `${seconds}s`;
  }

  stepStatus(step: Stage): StepStatus {
    if (STAGE_ORDER.indexOf(step) < STAGE_ORDER.indexOf(this.stage())) {
      return 'done';
    }
    if (this.stage() === step) {
      return 'active';
    }
    return 'pending';
  }

  safePreviewUrl(): SafeResourceUrl {
    return this.sanitizer.bypassSecurityTrustResourceUrl(this.previewUrl());
  }

  toggleFullscreenPreview(): void {
    this.isFullscreenPreview.set(!this.isFullscreenPreview());
  }

  openPreviewInNewTab(): void {
    window.open(this.previewUrl(), '_blank', 'noopener');
  }

  tryAgain(): void {
    this.router.navigate(['/app']);
  }

  ngOnInit(): void {
    const projectId = this.route.snapshot.paramMap.get('id');
    if (!projectId) {
      this.router.navigate(['/app']);
      return;
    }
    this.startTicking();
    this.startSubstepCycling();
    this.startPolling(projectId);
  }

  ngOnDestroy(): void {
    this.pollSubscription?.unsubscribe();
    this.tickSubscription?.unsubscribe();
    this.substepSubscription?.unsubscribe();
  }

  private startTicking(): void {
    this.tickSubscription = timer(1000, 1000).subscribe(() => {
      this.elapsedSeconds.set(this.elapsedSeconds() + 1);
    });
  }

  private startSubstepCycling(): void {
    let lastStage: Stage | null = null;
    let index = -1;
    this.substepSubscription = timer(0, SUBSTEP_INTERVAL_MS).subscribe(() => {
      const currentStage = this.stage();
      const list = SUBSTEPS[currentStage] ?? [];
      if (list.length === 0) {
        this.subStatus.set('');
        return;
      }
      if (currentStage !== lastStage) {
        lastStage = currentStage;
        index = 0;
      } else {
        index = (index + 1) % list.length;
      }
      this.subStatus.set(list[index]);
    });
  }

  private stopLiveIndicators(): void {
    this.tickSubscription?.unsubscribe();
    this.substepSubscription?.unsubscribe();
  }

  private startPolling(projectId: string): void {
    this.pollSubscription = timer(0, POLL_INTERVAL_MS)
      .pipe(
        switchMap(() => this.api.getProjectStatus(projectId)),
        takeWhile((res) => !TERMINAL_STATUSES.has(res.status), true)
      )
      .subscribe({
        next: (res) => this.handleStatus(res),
        error: (err: HttpErrorResponse) => this.fail(err),
      });
  }

  private handleStatus(res: ProjectStatusResponse): void {
    this.status.set(res);
    const stage = stageOf(res.status);

    if (stage === 'error') {
      this.errorMessage.set(res.rejection_reason || 'Something went wrong. Please try again.');
      this.stage.set('error');
      this.stopLiveIndicators();
      return;
    }

    this.stage.set(stage);

    if (stage === 'ready' && res.generation) {
      this.previewUrl.set(`${API_BASE_URL}${res.generation.preview_url_path}`);
      this.stopLiveIndicators();
    }
  }

  private fail(err: HttpErrorResponse): void {
    const detail = err.error?.detail;
    this.errorMessage.set(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
    this.stage.set('error');
    this.stopLiveIndicators();
  }
}
