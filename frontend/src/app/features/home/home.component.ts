import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { PRICING_TIERS } from '../../core/pricing-tiers';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { GenerationDemoComponent } from '../../shared/ui/generation-demo/generation-demo.component';
import { IconAlertTriangle } from '../../shared/ui/icons/icons';
import { PricingTierComponent } from '../../shared/ui/pricing-tier/pricing-tier.component';
import { SiteMockComponent } from '../../shared/ui/site-mock/site-mock.component';
import { SpinnerComponent } from '../../shared/ui/spinner/spinner.component';

/** The blueprint's Hero page: URL submission + marketing sections only. The
 * live crawl/extract/generate progress lives on its own route
 * (GenerationProgressComponent) -- a successful submit navigates there. */
@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    AppHeaderComponent,
    ButtonComponent,
    GenerationDemoComponent,
    PricingTierComponent,
    SiteMockComponent,
    SpinnerComponent,
    IconAlertTriangle,
  ],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css',
})
export class HomeComponent implements OnInit {
  url = '';
  tosAccepted = false;

  readonly pricingTiers = PRICING_TIERS;
  readonly errorMessage = signal('');
  readonly isSubmitting = signal(false);
  readonly balance = signal<number | null>(null);

  // Marketing copy -- illustrative, not backed by real analytics yet.
  readonly stats = [
    { value: '<1 min', label: 'Median rebuild time' },
    { value: '100%', label: 'Your content, kept intact' },
    { value: '$0', label: 'To preview your redesign' },
  ];

  readonly steps = [
    {
      n: '01',
      title: 'You paste a URL',
      copy: 'We crawl what is publicly there — copy, images, structure, contact details — and keep your facts intact. Nothing is invented about your business.',
    },
    {
      n: '02',
      title: 'We rebuild it',
      copy: 'Your brand blueprint (colors, fonts, tone) is extracted automatically, then used to generate a modern, responsive redesign in the tier you choose.',
    },
    {
      n: '03',
      title: 'You preview, then decide',
      copy: 'Walk through the new site live in your browser. Nothing is published anywhere, and downloading it only spends credits once you are happy with it.',
    },
  ];

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
