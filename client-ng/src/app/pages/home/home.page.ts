import { NgTemplateOutlet } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  Globe,
  Loader2,
  LucideAngularModule,
  Minus,
  Shield,
  Sparkles,
  Star,
  Users,
  X,
  Zap,
} from 'lucide-angular';

import { AuthService } from '../../core/auth.service';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { WalletService } from '../../core/wallet.service';
import { BrandAssetsChoice, BrandAssetsDialogComponent } from '../../shared/components/brand-assets-dialog.component';
import { CreditPackGridComponent } from '../../shared/components/credit-pack-grid.component';
import { FaqAccordionComponent } from '../../shared/components/faq-accordion.component';
import { SectionHeaderComponent } from '../../shared/components/section-header.component';
import { ACCENTS } from '../../shared/design/accents';
import { rememberLastProjectId } from '../../shared/design/last-project';
import { CountUpComponent } from '../../shared/motion/count-up.component';
import { RevealDirective } from '../../shared/motion/reveal.directive';
import { UiButton } from '../../shared/ui/button.directive';
import { UiInput } from '../../shared/ui/primitives';
import {
  BRANDS,
  COMPARISON,
  DEMO_STEPS,
  FAQS,
  FEATURES,
  INDUSTRIES,
  LIVE_COUNTER,
  REASONS,
  STATS,
  STEPS,
  TESTIMONIALS,
  TRUST_BADGES,
} from './home-content';

/** The public homepage: blueprint §8 sections around the real URL submit.
 * submit() sends a signed-out visitor to /login; otherwise it opens the
 * logo / hero pop-up, whose Start button sends POST
 * /projects/with-brand-assets and then goes to /projects/:id. The ToS
 * checkbox is mandatory (no domain-ownership check exists). */
@Component({
  selector: 'app-home-page',
  standalone: true,
  imports: [
    NgTemplateOutlet,
    FormsModule,
    RouterLink,
    LucideAngularModule,
    UiButton,
    UiInput,
    RevealDirective,
    CountUpComponent,
    SectionHeaderComponent,
    CreditPackGridComponent,
    FaqAccordionComponent,
    BrandAssetsDialogComponent,
  ],
  templateUrl: './home.page.html',
})
export default class HomePage {
  url = '';
  tosAccepted = false;

  readonly errorMessage = signal('');
  readonly isSubmitting = signal(false);
  /** Errors from the submit itself (bad file, 402, ...) show inside the pop-up. */
  readonly dialogError = signal('');
  private readonly brandDialog = viewChild.required(BrandAssetsDialogComponent);

  protected readonly icons = { AlertTriangle, ArrowRight, Check, Globe, Loader2, Minus, Shield, Sparkles, Star, Users, X, Zap };
  protected readonly accents = ACCENTS;
  protected readonly counter = LIVE_COUNTER;
  protected readonly stats = STATS;
  protected readonly brandsDoubled = [...BRANDS, ...BRANDS];
  protected readonly steps = STEPS;
  protected readonly features = FEATURES;
  protected readonly industries = INDUSTRIES;
  protected readonly industryThumbs = [
    { src: '/assets/images/template-showcase/saas-tech.jpg', top: '-6%', left: '1%', rotate: -5 },
    { src: '/assets/images/template-showcase/creative-agency.jpg', top: '55%', left: '-1%', rotate: 4 },
    { src: '/assets/images/template-showcase/corporate-solutions.jpg', top: '4%', right: '0%', rotate: 5 },
    { src: '/assets/images/template-showcase/modern-ecommerce.jpg', top: '60%', right: '2%', rotate: -4 },
  ] as { src: string; top: string; left?: string; right?: string; rotate: number }[];
  protected readonly reasons = REASONS;
  protected readonly demoSteps = DEMO_STEPS;
  protected readonly comparison = COMPARISON;
  protected readonly testimonials = TESTIMONIALS;
  protected readonly trustBadges = TRUST_BADGES;
  protected readonly faqs = FAQS;

  constructor(
    private readonly api: RedoWebsApiService,
    private readonly auth: AuthService,
    private readonly router: Router,
    readonly wallet: WalletService,
  ) {}

  get hasUrl(): boolean {
    return this.url.trim().length > 0;
  }

  get canSubmit(): boolean {
    return this.hasUrl && this.tosAccepted && !this.isSubmitting();
  }

  /** "Upgrade My Website": checks the form, then opens the logo / hero
   * pop-up. The project is only created from the pop-up's Start button. */
  submit(): void {
    if (!this.canSubmit) {
      return;
    }

    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login']);
      return;
    }

    this.errorMessage.set('');
    // Same message the backend's 402 gives -- shown before the pop-up so
    // nobody picks files only to be refused. The backend still decides.
    const balance = this.wallet.balance();
    if (balance !== null && balance < 1) {
      this.errorMessage.set('Insufficient credits to start a generation');
      return;
    }

    this.dialogError.set('');
    this.brandDialog().open();
  }

  startGeneration(choice: BrandAssetsChoice): void {
    this.dialogError.set('');
    this.isSubmitting.set(true);

    this.api
      .submitProjectWithAssets(this.url.trim(), this.tosAccepted, choice.later, choice.logo, choice.hero)
      .subscribe({
        next: (res) => {
          this.wallet.refresh();
          rememberLastProjectId(res.project_id);
          this.isSubmitting.set(false);
          this.brandDialog().close(true);
          this.router.navigate(['/projects', res.project_id]);
        },
        error: (err: HttpErrorResponse) => {
          const detail = err.error?.detail;
          this.dialogError.set(
            typeof detail === 'string'
              ? detail
              : err.status === 413
                ? 'The images are too large. Please use files under 5 MB.'
                : 'Something went wrong. Please try again.',
          );
          this.isSubmitting.set(false);
        },
      });
  }

  scrollToHero(): void {
    document.getElementById('hero')?.scrollIntoView({ behavior: 'smooth' });
  }
}
