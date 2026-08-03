import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { interval, Subscription, switchMap, takeWhile, timer } from 'rxjs';

import { API_BASE_URL } from '../../core/api-config';
import { AuthService } from '../../core/auth.service';
import { ProjectStatusResponse } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { ParallaxHeroDirective } from '../../shared/directives/parallax-hero.directive';
import { BadgeComponent } from '../../shared/ui/badge/badge.component';
import { BrowserFrameComponent } from '../../shared/ui/browser-frame/browser-frame.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { CardComponent } from '../../shared/ui/card/card.component';
import { GoogleSignInButtonComponent } from '../../shared/ui/google-sign-in-button/google-sign-in-button.component';
import { IconContainerComponent } from '../../shared/ui/icon-container/icon-container.component';
import { IconAlertTriangle, IconCheck, IconExternalLink, IconMaximize2, IconX } from '../../shared/ui/icons/icons';
import { StepItemComponent } from '../../shared/ui/step-item/step-item.component';

type Stage = 'idle' | 'crawling' | 'extracting' | 'generating' | 'ready' | 'error';
type StepStatus = 'done' | 'active' | 'pending';

const STAGE_ORDER: Stage[] = ['crawling', 'extracting', 'generating'];

const TERMINAL_STATUSES = new Set(['ready', 'failed', 'rejected']);

const BACKEND_STATUS_TO_STAGE: Record<string, Stage> = {
  pending: 'crawling',
  crawling: 'crawling',
  crawled: 'extracting',
  extracting_blueprint: 'extracting',
  blueprint_ready: 'generating',
  generating: 'generating',
  ready: 'ready',
  failed: 'error',
  rejected: 'error',
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

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    FormsModule,
    ParallaxHeroDirective,
    BadgeComponent,
    ButtonComponent,
    CardComponent,
    IconContainerComponent,
    StepItemComponent,
    BrowserFrameComponent,
    GoogleSignInButtonComponent,
    IconAlertTriangle,
    IconCheck,
    IconMaximize2,
    IconExternalLink,
    IconX,
  ],
  templateUrl: './home.component.html',
})
export class HomeComponent implements OnInit, OnDestroy {
  url = '';
  tosAccepted = false;

  readonly stage = signal<Stage>('idle');
  readonly errorMessage = signal('');
  readonly status = signal<ProjectStatusResponse | null>(null);
  readonly previewUrl = signal('');
  readonly elapsedSeconds = signal(0);
  readonly subStatus = signal('');
  readonly isFullscreenPreview = signal(false);
  readonly authError = signal('');

  private pollSubscription?: Subscription;
  private tickSubscription?: Subscription;
  private substepSubscription?: Subscription;

  constructor(
    private readonly api: RedoWebsApiService,
    private readonly sanitizer: DomSanitizer,
    readonly auth: AuthService
  ) {}

  ngOnInit(): void {
    this.auth.refreshSession().subscribe();
  }

  get canSubmit(): boolean {
    return (
      this.auth.isAuthenticated() && this.url.trim().length > 0 && this.tosAccepted && !this.isBusy
    );
  }

  onGoogleCredential(idToken: string): void {
    this.authError.set('');
    this.auth.loginWithGoogle(idToken).subscribe({
      error: () => this.authError.set('Google sign-in failed. Please try again.'),
    });
  }

  signOut(): void {
    this.auth.logout().subscribe();
  }

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

  submit(): void {
    if (!this.canSubmit) {
      return;
    }

    this.errorMessage.set('');
    this.status.set(null);
    this.previewUrl.set('');
    this.elapsedSeconds.set(0);
    this.stage.set('crawling');
    this.startTicking();
    this.startSubstepCycling();

    this.api.submitProject(this.url.trim(), this.tosAccepted).subscribe({
      next: (submitRes) => this.startPolling(submitRes.project_id),
      error: (err: HttpErrorResponse) => this.fail(err),
    });
  }

  reset(): void {
    this.pollSubscription?.unsubscribe();
    this.tickSubscription?.unsubscribe();
    this.substepSubscription?.unsubscribe();
    this.url = '';
    this.tosAccepted = false;
    this.stage.set('idle');
    this.errorMessage.set('');
    this.status.set(null);
    this.previewUrl.set('');
    this.elapsedSeconds.set(0);
    this.subStatus.set('');
    this.isFullscreenPreview.set(false);
  }

  ngOnDestroy(): void {
    this.pollSubscription?.unsubscribe();
    this.tickSubscription?.unsubscribe();
    this.substepSubscription?.unsubscribe();
  }

  private startTicking(): void {
    this.tickSubscription?.unsubscribe();
    this.tickSubscription = interval(1000).subscribe(() => {
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
        next: (res) => this.handleStatus(res),
        error: (err: HttpErrorResponse) => this.fail(err),
      });
  }

  private handleStatus(res: ProjectStatusResponse): void {
    this.status.set(res);
    const stage = BACKEND_STATUS_TO_STAGE[res.status] ?? 'crawling';

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
    this.errorMessage.set(
      typeof detail === 'string' ? detail : 'Something went wrong. Please try again.'
    );
    this.stage.set('error');
    this.stopLiveIndicators();
  }
}
