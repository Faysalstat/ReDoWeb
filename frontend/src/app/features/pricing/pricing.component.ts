import { Component } from '@angular/core';

import { CreditPackGridComponent } from '../../shared/ui/credit-pack-grid/credit-pack-grid.component';
import { PublicNavComponent } from '../../shared/ui/public-nav/public-nav.component';

/** Public pricing page -- real, admin-configured credit packs and tier
 * download costs (see CreditPackGridComponent). */
@Component({
  selector: 'app-pricing',
  standalone: true,
  imports: [PublicNavComponent, CreditPackGridComponent],
  templateUrl: './pricing.component.html',
})
export class PricingComponent {}
