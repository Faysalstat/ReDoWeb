import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { PublicNavComponent } from '../../shared/public-nav.component';
import { RefitService } from '../../core/refit.service';
import { Plan } from '../../core/models';

@Component({
  selector: 'app-pricing',
  standalone: true,
  imports: [RouterLink, PublicNavComponent],
  templateUrl: './pricing.component.html',
  styleUrl: './pricing.component.scss',
})
export class PricingComponent {
  private readonly refit = inject(RefitService);
  readonly plans = toSignal(this.refit.plans(), { initialValue: [] as Plan[] });
  readonly matrix = toSignal(this.refit.planMatrix(), { initialValue: [] as { label: string; basic: string; pro: string; premium: string }[] });

  edge(id: string): string {
    if (id === 'pro') return 'var(--color-accent)';
    if (id === 'premium') return 'var(--color-neutral-800)';
    return 'var(--color-neutral-400)';
  }
}
