import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { RefitService } from '../../core/refit.service';

@Component({
  selector: 'app-checkout',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './checkout.component.html',
  styleUrl: './checkout.component.scss',
})
export class CheckoutComponent {
  private readonly refit = inject(RefitService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly planId = this.route.snapshot.queryParamMap.get('plan') ?? 'pro';
  readonly domain = this.refit.lastUrl() || 'brightwood-dental.com';
  readonly total = this.planId === 'basic' ? 19 : this.planId === 'premium' ? 149 : 49;

  form = { email: '', card: '', expiry: '', cvc: '', name: '', country: 'United Kingdom' };
  readonly countries = ['United Kingdom', 'United States', 'India', 'Germany'];

  pay(): void {
    this.refit.pay(this.planId).subscribe(() => this.router.navigate(['/dashboard']));
  }
}
