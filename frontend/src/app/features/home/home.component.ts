import { HttpErrorResponse } from '@angular/common/http';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { WalletService } from '../../core/wallet.service';
import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { GenerationDemoComponent } from '../../shared/ui/generation-demo/generation-demo.component';
import { IconAlertTriangle, IconArrowRight } from '../../shared/ui/icons/icons';
import { CreditPackGridComponent } from '../../shared/ui/credit-pack-grid/credit-pack-grid.component';
import { SpinnerComponent } from '../../shared/ui/spinner/spinner.component';

/** The public homepage: URL submission + marketing sections, reachable
 * without a session. submit() checks auth itself and routes a signed-out
 * visitor to /login instead of calling the API (see below) -- the route
 * itself carries no guard. The live crawl/extract/generate progress lives on
 * its own route (GenerationProgressComponent) -- a successful submit
 * navigates there. */
@Component({
  selector: 'app-home',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    AppHeaderComponent,
    ButtonComponent,
    GenerationDemoComponent,
    CreditPackGridComponent,
    SpinnerComponent,
    IconAlertTriangle,
    IconArrowRight,
  ],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css',
})
export class HomeComponent {
  url = '';
  tosAccepted = false;

  readonly errorMessage = signal('');
  readonly isSubmitting = signal(false);

  // Marketing copy -- illustrative, not backed by real analytics yet.
  readonly stats = [
    { value: '<30 min', label: 'Median rebuild time' },
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

  private readonly accentColors = ['var(--color-accent)', 'var(--color-accent-2)', 'var(--color-success)'];

  constructor(
    private readonly api: RedoWebsApiService,
    private readonly auth: AuthService,
    private readonly router: Router,
    readonly wallet: WalletService
  ) {}

  accentColor(index: number): string {
    return this.accentColors[index % this.accentColors.length];
  }

  get canSubmit(): boolean {
    return this.url.trim().length > 0 && this.tosAccepted && !this.isSubmitting();
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
        this.router.navigate(['/projects', res.project_id]);
      },
      error: (err: HttpErrorResponse) => {
        const detail = err.error?.detail;
        this.errorMessage.set(typeof detail === 'string' ? detail : 'Something went wrong. Please try again.');
        this.isSubmitting.set(false);
      },
    });
  }
}
