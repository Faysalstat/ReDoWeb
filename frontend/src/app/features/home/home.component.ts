import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { ParallaxHeroDirective } from '../../shared/directives/parallax-hero.directive';
import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';
import { BadgeComponent } from '../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { CardComponent } from '../../shared/ui/card/card.component';
import { GenerationDemoComponent } from '../../shared/ui/generation-demo/generation-demo.component';
import { IconContainerComponent } from '../../shared/ui/icon-container/icon-container.component';
import { IconAlertTriangle, IconLink } from '../../shared/ui/icons/icons';
import { PricingTierComponent } from '../../shared/ui/pricing-tier/pricing-tier.component';
import { SpinnerComponent } from '../../shared/ui/spinner/spinner.component';

interface PricingTier {
  name: string;
  price: string;
  period: string;
  tagline: string;
  features: string[];
  highlighted: boolean;
  ctaLabel: string;
}

// Placeholder pricing — dummy figures/copy, to be replaced with real tier data
// from the backend's `tiers` table once checkout is wired up.
const PRICING_TIERS: PricingTier[] = [
  {
    name: 'Basic',
    price: '$19',
    period: 'one-time',
    tagline: 'A clean, modern refresh of your current site.',
    features: ['1 full redesign', 'Modern responsive layout', 'Basic on-page SEO', 'Email support'],
    highlighted: false,
    ctaLabel: 'Get Started',
  },
  {
    name: 'Premium',
    price: '$39',
    period: 'one-time',
    tagline: 'Sharper copy and a more polished, on-brand result.',
    features: [
      'Everything in Basic',
      'Enhanced copywriting & tone matching',
      'Accessibility (WCAG) pass',
      'Priority generation queue',
    ],
    highlighted: true,
    ctaLabel: 'Get Started',
  },
  {
    name: 'Pro',
    price: '$79',
    period: 'one-time',
    tagline: 'Maximum design polish for sites that need to impress.',
    features: [
      'Everything in Premium',
      'Advanced layout & micro-interactions',
      'Full SEO + Open Graph tags',
      'Priority support',
    ],
    highlighted: false,
    ctaLabel: 'Get Started',
  },
];

/** The blueprint's Hero page: URL submission + marketing sections only. The
 * live crawl/extract/generate progress lives on its own route
 * (GenerationProgressComponent) -- a successful submit navigates there. */
@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    FormsModule,
    ParallaxHeroDirective,
    AppHeaderComponent,
    BadgeComponent,
    ButtonComponent,
    CardComponent,
    IconContainerComponent,
    GenerationDemoComponent,
    PricingTierComponent,
    SpinnerComponent,
    IconAlertTriangle,
    IconLink,
  ],
  templateUrl: './home.component.html',
})
export class HomeComponent implements OnInit {
  url = '';
  tosAccepted = false;

  readonly pricingTiers = PRICING_TIERS;
  readonly errorMessage = signal('');
  readonly isSubmitting = signal(false);
  readonly balance = signal<number | null>(null);

  constructor(
    private readonly api: RedoWebsApiService,
    private readonly router: Router
  ) {}

  get canSubmit(): boolean {
    return this.url.trim().length > 0 && this.tosAccepted && !this.isSubmitting();
  }

  ngOnInit(): void {
    this.api.getWallet().subscribe((wallet) => this.balance.set(wallet.balance));
  }

  submit(): void {
    if (!this.canSubmit) {
      return;
    }

    this.errorMessage.set('');
    this.isSubmitting.set(true);

    this.api.submitProject(this.url.trim(), this.tosAccepted).subscribe({
      next: (res) => this.router.navigate(['/projects', res.project_id]),
      error: (err: HttpErrorResponse) => {
        const detail = err.error?.detail;
        this.errorMessage.set(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
        this.isSubmitting.set(false);
      },
    });
  }
}
