import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AppNavComponent } from '../../shared/app-nav.component';
import { RefitService } from '../../core/refit.service';
import { Invoice } from '../../core/models';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [FormsModule, RouterLink, AppNavComponent],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
})
export class SettingsComponent {
  private readonly refit = inject(RefitService);
  readonly invoices = toSignal(this.refit.invoices(), { initialValue: [] as Invoice[] });

  readonly usedRegenerations = 4;
  readonly includedRegenerations = 10;
  billing = { company: 'Brightwood Dental Ltd', vat: '' };

  get usagePercent(): number {
    return (this.usedRegenerations / this.includedRegenerations) * 100;
  }
}
