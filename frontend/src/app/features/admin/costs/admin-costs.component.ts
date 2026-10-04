import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { AdminApiService } from '../core/admin-api.service';
import {
  AdminCostByProjectRow,
  AdminCostByUserRow,
  AdminModelCostRow,
  AdminModelPricingRow,
} from '../core/admin-api.models';

type CostTab = 'model' | 'user' | 'project';

const RANGE_PRESETS = [7, 30, 90] as const;

/** Token/AI-cost breakdowns beyond the overview's aggregate numbers, plus
 * admin CRUD over the ModelPricing table that those costs are computed
 * from -- kept on one page/route rather than splitting cost-breakdown and
 * pricing-editor into separate routes for a page this narrow in scope. */
@Component({
  selector: 'app-admin-costs',
  standalone: true,
  imports: [FormsModule, SpinnerComponent, ButtonComponent],
  templateUrl: './admin-costs.component.html',
})
export class AdminCostsComponent implements OnInit {
  readonly rangePresets = RANGE_PRESETS;
  readonly selectedDays = signal<number>(30);
  readonly activeTab = signal<CostTab>('model');

  readonly byModel = signal<AdminModelCostRow[]>([]);
  readonly byUser = signal<AdminCostByUserRow[]>([]);
  readonly byProject = signal<AdminCostByProjectRow[]>([]);
  readonly pricing = signal<AdminModelPricingRow[]>([]);
  readonly pricingDrafts = signal<Record<string, { prompt: number; completion: number }>>({});

  readonly loading = signal(true);
  readonly errorMessage = signal('');
  readonly savingModel = signal<string | null>(null);
  readonly newModelName = signal('');
  readonly newModelPromptPrice = signal<number | null>(null);
  readonly newModelCompletionPrice = signal<number | null>(null);

  constructor(private readonly api: AdminApiService) {}

  ngOnInit(): void {
    this.load();
  }

  selectRange(days: number): void {
    if (days === this.selectedDays()) return;
    this.selectedDays.set(days);
    this.load();
  }

  selectTab(tab: CostTab): void {
    this.activeTab.set(tab);
  }

  formatUsd(value: number): string {
    return `$${value.toFixed(4)}`;
  }

  draftFor(modelName: string): { prompt: number; completion: number } {
    return this.pricingDrafts()[modelName] ?? { prompt: 0, completion: 0 };
  }

  setDraft(modelName: string, field: 'prompt' | 'completion', value: number): void {
    this.pricingDrafts.update((drafts) => ({
      ...drafts,
      [modelName]: { ...this.draftFor(modelName), [field]: value },
    }));
  }

  savePricing(modelName: string): void {
    const draft = this.draftFor(modelName);
    this.savingModel.set(modelName);
    this.api
      .upsertModelPricing(modelName, {
        prompt_price_per_1m: draft.prompt,
        completion_price_per_1m: draft.completion,
      })
      .subscribe({
        next: () => {
          this.savingModel.set(null);
          this.loadPricing();
        },
        error: () => {
          this.savingModel.set(null);
          this.errorMessage.set(`Failed to save pricing for ${modelName}.`);
        },
      });
  }

  addNewModelPricing(): void {
    const modelName = this.newModelName().trim();
    if (!modelName || this.newModelPromptPrice() === null || this.newModelCompletionPrice() === null) {
      this.errorMessage.set('Model name and both prices are required.');
      return;
    }
    this.savingModel.set(modelName);
    this.api
      .upsertModelPricing(modelName, {
        prompt_price_per_1m: this.newModelPromptPrice()!,
        completion_price_per_1m: this.newModelCompletionPrice()!,
      })
      .subscribe({
        next: () => {
          this.savingModel.set(null);
          this.newModelName.set('');
          this.newModelPromptPrice.set(null);
          this.newModelCompletionPrice.set(null);
          this.loadPricing();
        },
        error: () => {
          this.savingModel.set(null);
          this.errorMessage.set(`Failed to add pricing for ${modelName}.`);
        },
      });
  }

  private load(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    const days = this.selectedDays();

    this.api.getCostByModel(days).subscribe({ next: (res) => this.byModel.set(res.items) });
    this.api.getCostByUser(days).subscribe({ next: (res) => this.byUser.set(res.items) });
    this.api.getCostByProject(days).subscribe({
      next: (res) => {
        this.byProject.set(res.items);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load cost breakdowns.');
        this.loading.set(false);
      },
    });
    this.loadPricing();
  }

  private loadPricing(): void {
    this.api.listModelPricing().subscribe({
      next: (res) => {
        this.pricing.set(res.items);
        const drafts: Record<string, { prompt: number; completion: number }> = {};
        for (const row of res.items) {
          drafts[row.model_name] = { prompt: row.prompt_price_per_1m, completion: row.completion_price_per_1m };
        }
        this.pricingDrafts.set(drafts);
      },
    });
  }
}
