import { NgTemplateOutlet } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, signal } from '@angular/core';
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
  LIVE_COUNTER,
  REASONS,
  STATS,
  STEPS,
  TESTIMONIALS,
  TRUST_BADGES,
} from './home-content';

/** The public homepage: blueprint §8 sections around the real URL submit.
 * submit() is frontend/'s HomeComponent logic unchanged: a signed-out
 * visitor goes to /login, otherwise POST /projects then /projects/:id. The
 * ToS checkbox is mandatory (no domain-ownership check exists). */
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
  ],
  templateUrl: './home.page.html',
})
export default class HomePage {
  url = '';
  tosAccepted = false;

  readonly errorMessage = signal('');
  readonly isSubmitting = signal(false);

  protected readonly icons = { AlertTriangle, ArrowRight, Check, Globe, Loader2, Minus, Shield, Sparkles, Star, Users, X, Zap };
  protected readonly accents = ACCENTS;
  protected readonly counter = LIVE_COUNTER;
  protected readonly stats = STATS;
  protected readonly brandsDoubled = [...BRANDS, ...BRANDS];
  protected readonly steps = STEPS;
  protected readonly features = FEATURES;
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

  submit(): void {
    if (!this.canSubmit) {
      return;
    }

    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login']);
      return;
    }

    this.errorMessage.set('');
    this.isSubmitting.set(true);

    this.api.submitProject(this.url.trim(), this.tosAccepted).subscribe({
      next: (res) => {
        this.wallet.refresh();
        rememberLastProjectId(res.project_id);
        this.router.navigate(['/projects', res.project_id]);
      },
      error: (err: HttpErrorResponse) => {
        const detail = err.error?.detail;
        this.errorMessage.set(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
        this.isSubmitting.set(false);
      },
    });
  }

  scrollToHero(): void {
    document.getElementById('hero')?.scrollIntoView({ behavior: 'smooth' });
  }
}
