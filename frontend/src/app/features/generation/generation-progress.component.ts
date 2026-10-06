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
  InsufficientCreditsDetail,
  JobProgress,
  ProjectGenerationSummary,
  ProjectStatusResponse,
  ProjectTierActions,
  TierActionStatus,
} from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { WalletService } from '../../core/wallet.service';
import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';
import { BrowserFrameComponent } from '../../shared/ui/browser-frame/browser-frame.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { CardComponent } from '../../shared/ui/card/card.component';
import {
  IconAlertTriangle,
  IconCheck,
  IconExternalLink,
  IconLock,
  IconMaximize2,
  IconSparkles,
  IconX,
} from '../../shared/ui/icons/icons';
import { StepItemComponent, StepStatus } from '../../shared/ui/step-item/step-item.component';

type Device = 'desktop' | 'phone';
type BuyState = 'idle' | 'buying' | 'failed' | 'needs-credits';
type DownloadState = 'idle' | 'downloading' | 'failed';
type TierAction = 'full_site' | 'seo';

const NO_TIER_ACTIONS: ProjectTierActions = {
  full_site_status: 'none',
  seo_available: false,
  seo_status: 'none',
};

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
    IconLock,
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
  /** Per-tier Buy state -- 'buying' while POST /purchase is in flight,
   * 'needs-credits' after a 402 (drives the top-up prompt). */
  readonly buyStatus = signal<Record<string, BuyState>>({});
  /** Per-tier ZIP download state (purchase already happened). */
  readonly downloadStatus = signal<Record<string, DownloadState>>({});
  /** Set per tier when POST /purchase answers 402 -- drives the "needs N
   * more credits" prompt and its exact Top Up amount. */
  readonly downloadShortfall = signal<Record<string, InsufficientCreditsDetail>>({});
  /** Generate all pages / Run SEO click in flight, per tier. */
  readonly actionStarting = signal<Record<string, TierAction | null>>({});
  /** Last error from starting an action, per tier (the job's own failure
   * reason comes from status().tier_actions instead). */
  readonly actionError = signal<Record<string, string>>({});
  /** Download credit cost per enabled tier, from the public GET /tiers. */
  readonly tierCosts = signal<Record<string, number>>({});
  /** Tiers paid for during this visit, on top of status().purchased_tiers
   * (which only refreshes on the next poll). */
  private readonly paidThisSession = signal<string[]>([]);
  /** ?download=<tier> -- History's "Download" link: downloads the ZIP
   * automatically, but only for a tier that's already purchased. */
  private pendingAutoDownload: string | null = null;
  /** ?buy=<tier> -- set by the Top Up return URL so the purchase the user
   * was trying to make resumes automatically after paying. */
  private pendingAutoBuy: string | null = null;
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
  /** Follows running Generate all pages / Run SEO jobs. Separate from
   * pollSubscription on purpose: that one stops at the terminal "ready"
   * project status, which a purchased project already has. */
  private actionPollSubscription?: Subscription;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly router: Router,
    private readonly api: RedoWebsApiService,
    private readonly preview: PreviewService,
    private readonly sanitizer: DomSanitizer,
    readonly wallet: WalletService
  ) {}

  isPurchased(tier: string): boolean {
    return (this.status()?.purchased_tiers ?? []).includes(tier) || this.paidThisSession().includes(tier);
  }

  tierCost(tier: string): number | null {
    return this.tierCosts()[tier] ?? null;
  }

  tierActions(tier: string): ProjectTierActions {
    return this.status()?.tier_actions?.[tier] ?? NO_TIER_ACTIONS;
  }

  /** "Generate all pages" only exists for multi-page sites. */
  hasMorePages(): boolean {
    return (this.status()?.page_count ?? 1) > 1;
  }

  pageCount(): number {
    return this.status()?.page_count ?? 1;
  }

  fullSiteStatus(tier: string): TierActionStatus {
    return this.tierActions(tier).full_site_status;
  }

  seoStatus(tier: string): TierActionStatus {
    return this.tierActions(tier).seo_status;
  }

  /** Run SEO waits for "Generate all pages" on a multi-page site, so SEO
   * always runs on the final site. A single-page site is already complete. */
  seoNeedsAllPages(tier: string): boolean {
    return this.hasMorePages() && this.fullSiteStatus(tier) !== 'succeeded';
  }

  canGenerateAllPages(tier: string): boolean {
    const status = this.fullSiteStatus(tier);
    return this.isPurchased(tier) && !this.actionStarting()[tier] && (status === 'none' || status === 'failed');
  }

  canRunSeo(tier: string): boolean {
    const status = this.seoStatus(tier);
    return (
      this.isPurchased(tier) &&
      this.tierActions(tier).seo_available &&
      !this.seoNeedsAllPages(tier) &&
      !this.actionStarting()[tier] &&
      (status === 'none' || status === 'failed')
    );
  }

  /** "3 of 6" for the running step of a job's progress checklist. */
  stepPosition(progress: JobProgress): string {
    const index = progress.steps.findIndex((step) => step.key === progress.step);
    return `${index < 0 ? 1 : index + 1} of ${progress.steps.length}`;
  }

  /** What the ZIP holds right now -- mirrors the backend's download
   * preference (SEO version, then all pages, then the home page). */
  zipContents(tier: string): string {
    const pages = this.hasMorePages() && this.fullSiteStatus(tier) === 'succeeded';
    const seo = this.seoStatus(tier) === 'succeeded';
    if (seo) {
      return pages || !this.hasMorePages() ? 'Full site, SEO optimized' : 'Home page, SEO optimized';
    }
    if (!this.hasMorePages()) {
      return 'Full site (1 page)';
    }
    return pages ? `All ${this.pageCount()} pages` : 'Home page only';
  }

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
    this.navigateToCheckout(shortfall ?? null, null);
  }

  /** Top Up from the Buy prompt -- comes back to this project with
   * ?buy=<tier> so the purchase resumes on return. */
  topUpForBuy(tier: string): void {
    this.navigateToCheckout(this.downloadShortfall()[tier]?.shortfall ?? null, tier);
  }

  private navigateToCheckout(credits: number | null, resumeBuyTier: string | null): void {
    const projectId = this.route.snapshot.paramMap.get('id');
    const returnUrl = resumeBuyTier
      ? `/projects/${projectId}?buy=${encodeURIComponent(resumeBuyTier)}`
      : `/projects/${projectId}`;
    const queryParams: Record<string, string | number> = { returnUrl };
    if (credits) {
      queryParams['credits'] = credits;
    }
    this.router.navigate(['/checkout'], { queryParams });
  }

  ngOnInit(): void {
    const projectId = this.route.snapshot.paramMap.get('id');
    if (!projectId) {
      this.router.navigate(['/']);
      return;
    }
    this.pendingAutoDownload = this.route.snapshot.queryParamMap.get('download');
    this.pendingAutoBuy = this.route.snapshot.queryParamMap.get('buy');
    this.api.getTiers().subscribe({
      next: (res) =>
        this.tierCosts.set(Object.fromEntries(res.items.map((t) => [t.key, t.download_credit_cost]))),
      error: () => {},
    });
    this.startTicking();
    this.startSubstepCycling();
    this.startPolling(projectId);
  }

  ngOnDestroy(): void {
    this.pollSubscription?.unsubscribe();
    this.tickSubscription?.unsubscribe();
    this.substepSubscription?.unsubscribe();
    this.actionPollSubscription?.unsubscribe();
  }

  /** Buy a tier's design -- the only charge (idempotent per project+tier,
   * so buying again costs nothing). Unlocks Download ZIP, Generate all
   * pages and (Pro/Premium) Run SEO; starts nothing by itself. */
  buy(tier: string): void {
    const projectId = this.route.snapshot.paramMap.get('id');
    if (!projectId || this.buyStatus()[tier] === 'buying') {
      return;
    }
    this.setBuyStatus(tier, 'buying');
    this.api.purchaseTier(projectId, tier).subscribe({
      next: () => {
        if (!this.paidThisSession().includes(tier)) {
          this.paidThisSession.set([...this.paidThisSession(), tier]);
        }
        this.wallet.refresh();
        this.setBuyStatus(tier, 'idle');
      },
      error: (err: HttpErrorResponse) => {
        const detail = err.error?.detail;
        if (err.status === 402 && detail && typeof detail === 'object') {
          const short = detail as InsufficientCreditsDetail;
          this.downloadShortfall.set({ ...this.downloadShortfall(), [tier]: short });
          this.wallet.set(short.balance);
          this.setBuyStatus(tier, 'needs-credits');
        } else {
          this.setBuyStatus(tier, 'failed');
        }
      },
    });
  }

  /** Downloads the best finished output right now (SEO version, then all
   * pages, then the home page) -- no charge, the tier is already bought. */
  download(tier: string): void {
    const projectId = this.route.snapshot.paramMap.get('id');
    if (!projectId || !this.isPurchased(tier)) {
      return;
    }
    this.setDownloadStatus(tier, 'downloading');
    this.api.downloadFile(projectId, tier).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `${projectId}-${tier}.zip`;
        anchor.click();
        URL.revokeObjectURL(url);
        this.setDownloadStatus(tier, 'idle');
      },
      error: () => this.setDownloadStatus(tier, 'failed'),
    });
  }

  generateAllPages(tier: string): void {
    if (this.canGenerateAllPages(tier)) {
      this.startAction(tier, 'full_site');
    }
  }

  runSeo(tier: string): void {
    if (this.canRunSeo(tier)) {
      this.startAction(tier, 'seo');
    }
  }

  private startAction(tier: string, action: TierAction): void {
    const projectId = this.route.snapshot.paramMap.get('id');
    if (!projectId) {
      return;
    }
    this.actionStarting.set({ ...this.actionStarting(), [tier]: action });
    this.actionError.set({ ...this.actionError(), [tier]: '' });
    const request =
      action === 'full_site' ? this.api.startFullSite(projectId, tier) : this.api.startSeo(projectId, tier);
    request.subscribe({
      next: () => {
        this.actionStarting.set({ ...this.actionStarting(), [tier]: null });
        this.startActionPolling(projectId, true);
      },
      error: (err: HttpErrorResponse) => {
        this.actionStarting.set({ ...this.actionStarting(), [tier]: null });
        const detail = err.error?.detail;
        this.actionError.set({
          ...this.actionError(),
          [tier]: typeof detail === 'string' ? detail : 'Something went wrong — please try again.',
        });
        // A 409 usually means the state moved on (already running/done) --
        // refresh so the buttons reflect it.
        this.startActionPolling(projectId, true);
      },
    });
  }

  /** Polls the project while any tier's Generate all pages / Run SEO job is
   * running. `force` polls at least once even if nothing looks running yet
   * (right after a start click, before the next status shows the job). */
  private startActionPolling(projectId: string, force = false): void {
    if (!force && this.actionPollSubscription && !this.actionPollSubscription.closed) {
      return;
    }
    this.actionPollSubscription?.unsubscribe();
    this.actionPollSubscription = timer(0, POLL_INTERVAL_MS)
      .pipe(
        switchMap(() => this.api.getProjectStatus(projectId)),
        takeWhile((res) => anyTierActionRunning(res), true)
      )
      .subscribe({
        next: (res) => this.handleStatus(projectId, res),
        error: () => {},
      });
  }

  private setBuyStatus(tier: string, value: BuyState): void {
    this.buyStatus.set({ ...this.buyStatus(), [tier]: value });
  }

  private setDownloadStatus(tier: string, value: DownloadState): void {
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
      // A reload (or another tab) while Generate all pages / Run SEO runs:
      // keep following it.
      if (anyTierActionRunning(res)) {
        this.startActionPolling(projectId);
      }
    }
    this.resumePendingActions(res);
  }

  /** ?buy=<tier> (Top Up return) resumes the purchase; ?download=<tier>
   * (History link) downloads the ZIP, but only for a tier already bought --
   * otherwise it just selects the tier so its Buy button is in view. The
   * param is dropped afterwards so a refresh doesn't repeat it. */
  private resumePendingActions(res: ProjectStatusResponse): void {
    const buyTier = this.pendingAutoBuy;
    if (buyTier && res.generations.some((gen) => gen.tier === buyTier)) {
      this.pendingAutoBuy = null;
      this.selectedTier.set(buyTier);
      this.router.navigate([], { relativeTo: this.route, queryParams: {}, replaceUrl: true });
      this.buy(buyTier);
    }
    const downloadTier = this.pendingAutoDownload;
    if (downloadTier && res.generations.some((gen) => gen.tier === downloadTier)) {
      this.pendingAutoDownload = null;
      this.selectedTier.set(downloadTier);
      this.router.navigate([], { relativeTo: this.route, queryParams: {}, replaceUrl: true });
      if (this.isPurchased(downloadTier)) {
        this.download(downloadTier);
      }
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

function anyTierActionRunning(res: ProjectStatusResponse): boolean {
  return Object.values(res.tier_actions ?? {}).some(
    (actions) => actions.full_site_status === 'running' || actions.seo_status === 'running'
  );
}
