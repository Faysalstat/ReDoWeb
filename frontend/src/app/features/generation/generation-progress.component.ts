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
import {
  ProjectGenerationSummary,
  ProjectStatusResponse,
} from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';
import { BrowserFrameComponent } from '../../shared/ui/browser-frame/browser-frame.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { CardComponent } from '../../shared/ui/card/card.component';
import {
  IconAlertTriangle,
  IconCheck,
  IconExternalLink,
  IconMaximize2,
  IconSparkles,
  IconX,
} from '../../shared/ui/icons/icons';
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
    ButtonComponent,
    CardComponent,
    StepItemComponent,
    BrowserFrameComponent,
    IconAlertTriangle,
    IconCheck,
    IconMaximize2,
    IconExternalLink,
    IconSparkles,
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
  /** Per-tier download state -- 'idle' until the user clicks, 'starting'
   * while POST /download is in flight, 'building' while a multi-page
   * project's full-site job runs (polled), then 'ready'/'failed'. */
  readonly downloadStatus = signal<Record<string, 'idle' | 'starting' | 'building' | 'ready' | 'failed'>>(
    {}
  );
  /** State for the awaiting_cost_approval screen (see
   * docs/generation-cost-gate-plan.md) -- `approving` while the Continue
   * click's POST is in flight. */
  readonly approving = signal(false);
  readonly approveError = signal('');
  /** Tiers whose retry POST is in flight, so each failed tier's button can
   * show its own pending state independently. */
  readonly retryingTiers = signal<string[]>([]);
  readonly retryError = signal('');

  get frameWidth(): number {
    return this.device() === 'phone' ? 360 : 900;
  }

  private pollSubscription?: Subscription;
  private tickSubscription?: Subscription;
  private substepSubscription?: Subscription;
  private downloadPollSubscription?: Subscription;

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
      // Tiers now fan out and can run concurrently, so there's no single
      // "current tier" position -- list whichever ones are actually running.
      const runningLabels = s.current_tiers.map(tierLabel).join(', ');
      const suffix = runningLabels ? `: ${runningLabels}` : '';
      label += ` (${s.tiers_completed} of ${s.tiers_total} done${suffix})`;
    }
    return label;
  }

  /** Turns a prompt-file slug like "business_simpleweb_prompt" into a
   * readable label ("Business Simpleweb") for the results summary tile. */
  templateName(raw: string): string {
    return raw
      .replace(/_prompt$/i, '')
      .split(/[_-]+/)
      .filter(Boolean)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
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
    this.router.navigate(['/']);
  }

  /** "rejected" means the site itself is out of scope (too many pages,
   * blocks crawling, requires login) -- distinct from "failed", a system
   * error on our end. Same visual treatment either way, just different
   * framing so a site-side limitation doesn't read as "we broke". */
  errorHeading(): string {
    return this.status()?.status === 'rejected' ? "We couldn't process this site" : 'Something went wrong';
  }

  isRetrying(tier: string): boolean {
    return this.retryingTiers().includes(tier);
  }

  /** Re-runs one failed tier. The other tiers' finished previews stay
   * exactly as they are; only this tier rebuilds, against the blueprint
   * already on disk and at no extra credit cost. Polling has usually
   * already stopped by now (the project sits at the terminal "ready" or
   * "failed"), so it's restarted to follow the new attempt. */
  retryTier(tier: string): void {
    const projectId = this.route.snapshot.paramMap.get('id');
    if (!projectId || this.isRetrying(tier)) {
      return;
    }
    this.retryError.set('');
    this.retryingTiers.set([...this.retryingTiers(), tier]);
    this.api.retryTier(projectId, tier).subscribe({
      next: () => {
        this.retryingTiers.set(this.retryingTiers().filter((key) => key !== tier));
        this.errorMessage.set('');
        this.stage.set('generating');
        this.startTicking();
        this.startSubstepCycling();
        this.startPolling(projectId);
      },
      error: () => {
        this.retryingTiers.set(this.retryingTiers().filter((key) => key !== tier));
        this.retryError.set(`Couldn't restart the ${tierLabel(tier)} tier — please try again.`);
      },
    });
  }

  /** Continue click on the awaiting_cost_approval screen -- a 200 with
   * approved: false (insufficient balance) is a normal outcome, not an
   * error; the next 3s poll tick picks up whatever project.status/cost_gate
   * is current either way, so there's nothing else to react to here. */
  approveGeneration(): void {
    const projectId = this.route.snapshot.paramMap.get('id');
    if (!projectId) {
      return;
    }
    this.approving.set(true);
    this.approveError.set('');
    this.api.approveGeneration(projectId).subscribe({
      next: () => this.approving.set(false),
      error: () => {
        this.approving.set(false);
        this.approveError.set('Something went wrong — please try again.');
      },
    });
  }

  /** Top Up click when the wallet balance is short -- routes into the
   * existing (unwired) checkout page with the shortfall threaded through,
   * so wiring a real payment gateway later doesn't need this seam
   * re-plumbed. */
  goToTopUp(): void {
    const shortfall = this.status()?.cost_gate?.shortfall_credits;
    this.router.navigate(['/checkout'], { queryParams: shortfall ? { credits: shortfall } : {} });
  }

  ngOnInit(): void {
    const projectId = this.route.snapshot.paramMap.get('id');
    if (!projectId) {
      this.router.navigate(['/']);
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
    this.downloadPollSubscription?.unsubscribe();
  }

  /** Starts (or resumes watching) a tier's download. Most projects are
   * single-page and come back "ready" immediately, same as an instant zip
   * download today; a multi-page project without a cached full-site build
   * yet comes back "building" and this switches to polling
   * getDownloadStatus, same timer/switchMap/takeWhile pattern startPolling
   * above uses for the main generation poll. */
  download(tier: string): void {
    const projectId = this.route.snapshot.paramMap.get('id');
    if (!projectId) {
      return;
    }
    this.setDownloadStatus(tier, 'starting');
    this.api.startDownload(projectId, tier).subscribe({
      next: (res) => (res.status === 'ready' ? this.fetchFile(projectId, tier) : this.pollDownload(projectId, tier)),
      error: () => this.setDownloadStatus(tier, 'failed'),
    });
  }

  private pollDownload(projectId: string, tier: string): void {
    this.setDownloadStatus(tier, 'building');
    this.downloadPollSubscription = timer(0, POLL_INTERVAL_MS)
      .pipe(
        switchMap(() => this.api.getDownloadStatus(projectId, tier)),
        takeWhile((res) => res.status === 'building', true)
      )
      .subscribe((res) => {
        if (res.status === 'ready') {
          this.fetchFile(projectId, tier);
        } else if (res.status === 'failed') {
          this.setDownloadStatus(tier, 'failed');
        }
      });
  }

  private fetchFile(projectId: string, tier: string): void {
    this.api.downloadFile(projectId, tier).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `${projectId}-${tier}.zip`;
        anchor.click();
        URL.revokeObjectURL(url);
        this.setDownloadStatus(tier, 'ready');
      },
      error: () => this.setDownloadStatus(tier, 'failed'),
    });
  }

  private setDownloadStatus(tier: string, value: 'idle' | 'starting' | 'building' | 'ready' | 'failed'): void {
    this.downloadStatus.set({ ...this.downloadStatus(), [tier]: value });
  }

  // The three start* methods below unsubscribe first so they're safe to
  // call again mid-session -- retryTier() restarts all three after the
  // poll has already terminated on a previous terminal status.
  private startTicking(): void {
    this.tickSubscription?.unsubscribe();
    this.tickSubscription = timer(1000, 1000).subscribe(() => {
      this.elapsedSeconds.set(this.elapsedSeconds() + 1);
    });
  }

  private startSubstepCycling(): void {
    this.substepSubscription?.unsubscribe();
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
    this.pollSubscription?.unsubscribe();
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

  /** Called when the status-poll request itself fails (as opposed to the
   * project reaching a terminal failed/rejected status normally) -- e.g.
   * the backend is unreachable, or the project id doesn't exist/isn't the
   * caller's. Distinguished from handleStatus()'s rejection_reason path so
   * a dropped connection doesn't get mistaken for a site-crawl failure. */
  private fail(err: HttpErrorResponse): void {
    const detail = err.error?.detail;
    if (typeof detail === 'string') {
      this.errorMessage.set(detail);
    } else if (err.status === 0) {
      this.errorMessage.set("Couldn't reach the server. Check your connection and try again.");
    } else {
      this.errorMessage.set('Something went wrong. Please try again.');
    }
    this.stage.set('error');
    this.stopLiveIndicators();
  }
}
