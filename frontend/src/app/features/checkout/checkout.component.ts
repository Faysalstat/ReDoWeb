import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { PRICING_TIERS } from '../../core/pricing-tiers';

/** Standalone checkout page. Not wired to Stripe or any backend endpoint yet
 * -- submitting just navigates to History, matching how far the real
 * download/payment flow has been built. See docs/PROGRESS.md. */
@Component({
  selector: 'app-checkout',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './checkout.component.html',
  styleUrl: './checkout.component.css',
})
export class CheckoutComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  private readonly tierName = this.route.snapshot.queryParamMap.get('tier') ?? 'Pro';
  readonly tier = PRICING_TIERS.find((t) => t.name.toLowerCase() === this.tierName.toLowerCase()) ?? PRICING_TIERS[0];
  /** Set when arriving from the cost-gate modal's Top Up button (see
   * generation-progress.component.ts) -- the number of credits the user was
   * short. No real purchase-N-credits flow exists yet (this whole page is a
   * Stripe-less mockup), but threading the value through here means wiring
   * a real payment gateway later doesn't need this seam re-plumbed. */
  readonly requestedCredits = Number(this.route.snapshot.queryParamMap.get('credits')) || null;

  form = { email: '', card: '', expiry: '', cvc: '', name: '', country: 'United Kingdom' };
  readonly countries = ['United Kingdom', 'United States', 'India', 'Germany'];

  pay(): void {
    this.router.navigate(['/history']);
  }
}
