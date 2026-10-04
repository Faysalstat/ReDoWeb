import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AppHeaderComponent } from '../../shared/ui/app-header/app-header.component';

interface Invoice {
  date: string;
  description: string;
  amount: number;
  status: 'Paid' | 'Refunded' | 'Failed';
}

// Placeholder invoice history -- this page isn't wired to a real billing
// backend yet. See docs/PROGRESS.md.
const INVOICES: Invoice[] = [
  { date: '12 Aug 2026', description: 'Pro tier download', amount: 79, status: 'Paid' },
  { date: '02 Aug 2026', description: 'Premium tier download', amount: 39, status: 'Paid' },
  { date: '18 Jul 2026', description: 'Basic tier download', amount: 19, status: 'Refunded' },
];

/** Standalone billing/settings page. Not wired to a real subscription or
 * payment-method backend yet -- credits are the real spend model
 * (see CLAUDE.md); this page previews what a billing-history view could
 * look like once that's built out. */
@Component({
  selector: 'app-billing-settings',
  standalone: true,
  imports: [FormsModule, RouterLink, AppHeaderComponent],
  templateUrl: './billing-settings.component.html',
  styleUrl: './billing-settings.component.css',
})
export class BillingSettingsComponent {
  readonly invoices = INVOICES;

  billing = { company: '', vat: '' };
}
