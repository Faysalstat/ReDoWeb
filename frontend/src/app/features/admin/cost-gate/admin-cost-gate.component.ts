import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminCostSettingResponse } from '../core/admin-api.models';

/** The two global settings behind the pre-generation cost-estimate gate
 * (see docs/generation-cost-gate-plan.md): the USD threshold above which
 * tasks_blueprint.py pauses a project for approval, and the USD-per-credit
 * rate used to convert that estimate into a required wallet balance. Both
 * are a single admin-editable float with the same row-present-wins-else-
 * config-default semantics, so one component/template covers both. */
@Component({
  selector: 'app-admin-cost-gate',
  standalone: true,
  imports: [FormsModule, DatePipe, SpinnerComponent, ButtonComponent],
  templateUrl: './admin-cost-gate.component.html',
})
export class AdminCostGateComponent implements OnInit {
  readonly threshold = signal<AdminCostSettingResponse | null>(null);
  readonly usdPerCredit = signal<AdminCostSettingResponse | null>(null);
  readonly thresholdDraft = signal<number | null>(null);
  readonly usdPerCreditDraft = signal<number | null>(null);
  readonly loading = signal(true);
  readonly errorMessage = signal('');
  readonly savedMessage = signal('');
  readonly savingThreshold = signal(false);
  readonly savingRate = signal(false);

  constructor(private readonly api: AdminApiService) {}

  ngOnInit(): void {
    this.load();
  }

  saveThreshold(): void {
    const value = this.thresholdDraft();
    if (value === null || value < 0) {
      this.errorMessage.set('Alert threshold must be a non-negative number.');
      return;
    }
    this.errorMessage.set('');
    this.savedMessage.set('');
    this.savingThreshold.set(true);
    this.api.updateCostAlertThreshold({ value }).subscribe({
      next: (res) => {
        this.savingThreshold.set(false);
        this.threshold.set(res);
        this.savedMessage.set('Saved alert threshold.');
      },
      error: () => {
        this.savingThreshold.set(false);
        this.errorMessage.set('Failed to save alert threshold.');
      },
    });
  }

  saveUsdPerCredit(): void {
    const value = this.usdPerCreditDraft();
    if (value === null || value <= 0) {
      this.errorMessage.set('USD-per-credit rate must be a positive number.');
      return;
    }
    this.errorMessage.set('');
    this.savedMessage.set('');
    this.savingRate.set(true);
    this.api.updateUsdPerCredit({ value }).subscribe({
      next: (res) => {
        this.savingRate.set(false);
        this.usdPerCredit.set(res);
        this.savedMessage.set('Saved USD-per-credit rate.');
      },
      error: () => {
        this.savingRate.set(false);
        this.errorMessage.set('Failed to save USD-per-credit rate.');
      },
    });
  }

  private load(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.api.getCostAlertThreshold().subscribe({
      next: (res) => {
        this.threshold.set(res);
        this.thresholdDraft.set(res.value);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load cost-gate settings.');
        this.loading.set(false);
      },
    });
    this.api.getUsdPerCredit().subscribe({
      next: (res) => {
        this.usdPerCredit.set(res);
        this.usdPerCreditDraft.set(res.value);
      },
    });
  }
}
