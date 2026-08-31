import { Component } from '@angular/core';

import { PRICING_MATRIX, PRICING_TIERS } from '../../core/pricing-tiers';
import { PricingTierComponent } from '../../shared/ui/pricing-tier/pricing-tier.component';
import { PublicNavComponent } from '../../shared/ui/public-nav/public-nav.component';

/** Standalone pricing/plan-comparison page. Not wired to a real checkout or
 * the backend's `tiers` table yet -- see docs/PROGRESS.md. Uses the same
 * placeholder PRICING_TIERS constant as the home page's embedded pricing
 * section so the two never drift out of sync. */
@Component({
  selector: 'app-pricing',
  standalone: true,
  imports: [PublicNavComponent, PricingTierComponent],
  templateUrl: './pricing.component.html',
})
export class PricingComponent {
  readonly tiers = PRICING_TIERS;
  readonly matrix = PRICING_MATRIX;
}
