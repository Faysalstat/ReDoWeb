import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription, switchMap, takeWhile, timer } from 'rxjs';

import { PreviewService } from '../../core/preview.service';
import {
  STAGE_ORDER,
  Stage,
  TERMINAL_STATUSES,
  stageOf,
  statusLabel,
  tierLabel,
} from '../../core/project-status';
import { ProjectGenerationSummary, ProjectStatusResponse } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';
import { BadgeComponent } from '../../shared/ui/badge/badge.component';
import { BrowserFrameComponent } from '../../shared/ui/browser-frame/browser-frame.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { CardComponent } from '../../shared/ui/card/card.component';
import { IconAlertTriangle, IconExternalLink, IconMaximize2, IconX } from '../../shared/ui/icons/icons';
import { SiteMockComponent } from '../../shared/ui/site-mock/site-mock.component';
import { StepItemComponent, StepStatus } from '../../shared/ui/step-item/step-item.component';

type Device = 'desktop' | 'phone';

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
    StepItemComponent,
    BrowserFrameComponent,
    SiteMockComponent,
    IconAlertTriangle,
    IconMaximize2,
    IconExternalLink,
    IconX,
  ],
  templateUrl: './generation-progress.component.html',
  styleUrl: './generation-progress.component.css',
})
export class GenerationProgressComponent implements OnInit, OnDestroy {
  readonly stage = signal<Stage>('crawling');
  readonly errorMessage = signal('');
  readonly status = signal<ProjectStatusResponse | null>(null);
  /** Authed preview URL per tier key, fetched once per tier as each one
   * finishes generating and cached here so switching tabs doesn't re-mint a
   * token every click. */
  readonly previewUrls = signal<Record<string, string>>({});
  readonly selectedTier = signal<string | null>(null);
  readonly elapsedSeconds = signal(0);
  readonly subStatus = signal('');
  readonly isFullscreenPreview = signal(false);
  readonly device = signal<Device>('desktop');
  readonly tierLabel = tierLabel;

  get frameWidth(): number {
    return this.device() === 'phone' ? 360 : 900;
  }

  private pollSubscription?: Subscription;
  private tickSubscription?: Subscription;
  private substepSubscription?: Subscription;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly api: RedoWebsApiService,
    private readonly preview: PreviewService,
    private readonly sanitizer: DomSanitizer
  ) {}

  get isBusy(): boolean {
    return STAGE_ORDER.includes(this.stage());
  }

  get progressPercent(): number {
    const stage = this.stage();
    const idx = STAGE_ORDER.indexOf(stage);
    if (idx < 0) {
      return 0;
    }
    const stageWidth = 100 / STAGE_ORDER.length;
    const completedWidth = idx * stageWidth;
    // "Generating" now covers every enabled tier run sequentially (could be
    // 3x as long as a single tier), so fill that last band proportionally
    // to tiers finished so far instead of jumping straight to 100% the
    // moment tier 1 of 3 starts.
    if (stage === 'generating') {
      const s = this.status();
      const fraction = s && s.tiers_total > 0 ? s.tiers_completed / s.tiers_total : 0;
      return Math.round(completedWidth + stageWidth * fraction);
    }
    return Math.round(completedWidth + stageWidth);
  }

  get formattedElapsed(): string {
    const total = this.elapsedSeconds();
    const minutes = Math.floor(total / 60);
    const seconds = total % 60;
    return minutes > 0 ? `${minutes}:${seconds.toString().padStart(2, '0')}` : `${seconds}s`;
  }

  statusLabelFor(stage: Stage): string {
    const idx = STAGE_ORDER.indexOf(stage);
    if (idx < 0) {
      return statusLabel(this.status()?.status ?? '');
    }
    let label = `Step ${idx + 1} of ${STAGE_ORDER.length} — ${statusLabel(this.status()?.status ?? '')}`;
    const s = this.status();
    if (stage === 'generating' && s && s.tiers_total > 1) {
      const tierNum = Math.min(s.tiers_completed + 1, s.tiers_total);
      const suffix = s.current_tier ? `: ${tierLabel(s.current_tier)}` : '';
      label += ` (tier ${tierNum} of ${s.tiers_total}${suffix})`;
    }
    return label;
  }

  activeGeneration(): ProjectGenerationSummary | null {
    const tier = this.selectedTier();
    return this.status()?.generations.find((gen) => gen.tier === tier) ?? null;
  }

  activePreviewUrl(): string {
    const tier = this.selectedTier();
    return tier ? this.previewUrls()[tier] ?? '' : '';
  }

  selectTier(tier: string): void {
    this.selectedTier.set(tier);
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
    return this.sanitizer.bypassSecurityTrustResourceUrl(this.activePreviewUrl());
  }

  toggleFullscreenPreview(): void {
    this.isFullscreenPreview.set(!this.isFullscreenPreview());
  }

  openPreviewInNewTab(): void {
    window.open(this.activePreviewUrl(), '_blank', 'noopener');
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
        next: (res) => this.handleStatus(projectId, res),
        error: (err: HttpErrorResponse) => this.fail(err),
      });
  }

  private handleStatus(projectId: string, res: ProjectStatusResponse): void {
    this.status.set(res);
    const stage = stageOf(res.status);

    if (stage === 'error') {
      this.errorMessage.set(res.rejection_reason || 'Something went wrong. Please try again.');
      this.stage.set('error');
      this.stopLiveIndicators();
      return;
    }

    this.stage.set(stage);

    for (const gen of res.generations) {
      this.ensurePreviewUrl(projectId, gen);
    }
    if (this.selectedTier() === null && res.generations.length > 0) {
      this.selectedTier.set(res.generations[0].tier);
    }

    if (stage === 'ready') {
      this.stopLiveIndicators();
    }
  }

  /** Mints (once) and caches the authed iframe-loadable preview URL for one
   * tier's already-finished output, so re-polling or switching tabs never
   * re-requests a token for a tier already fetched. */
  private ensurePreviewUrl(projectId: string, gen: ProjectGenerationSummary): void {
    if (this.previewUrls()[gen.tier]) {
      return;
    }
    this.preview.getAuthedPreviewUrl(projectId, gen.preview_url_path).subscribe({
      next: (url) => this.previewUrls.set({ ...this.previewUrls(), [gen.tier]: url }),
      error: () => this.previewUrls.set({ ...this.previewUrls(), [gen.tier]: '' }),
    });
  }

  private fail(err: HttpErrorResponse): void {
    const detail = err.error?.detail;
    this.errorMessage.set(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
    this.stage.set('error');
    this.stopLiveIndicators();
  }
}
