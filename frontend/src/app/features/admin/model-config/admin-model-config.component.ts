import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { BadgeComponent } from '../../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminTierModelRow, AdminVisionModelResponse } from '../core/admin-api.models';

/** Per-tier generation-model override (Tier.generation_model) and the one
 * shared vision/review model (AIModelSetting keyed "vision_model", used by
 * every blueprint_review.py call -- there is no separate model for the
 * text content-review call vs. the vision meta call). Plain free-text
 * inputs, matching the DB's own looseness (no FK/enum to a models list). */
@Component({
  selector: 'app-admin-model-config',
  standalone: true,
  imports: [FormsModule, DatePipe, SpinnerComponent, ButtonComponent, BadgeComponent],
  templateUrl: './admin-model-config.component.html',
})
export class AdminModelConfigComponent implements OnInit {
  readonly tiers = signal<AdminTierModelRow[]>([]);
  readonly visionModel = signal<AdminVisionModelResponse | null>(null);
  readonly tierDrafts = signal<Record<string, string>>({});
  readonly visionDraft = signal('');
  readonly loading = signal(true);
  readonly errorMessage = signal('');
  readonly savingKey = signal<string | null>(null);
  readonly togglingKey = signal<string | null>(null);
  readonly savingVision = signal(false);
  readonly savedMessage = signal('');

  constructor(private readonly api: AdminApiService) {}

  ngOnInit(): void {
    this.load();
  }

  draftFor(key: string): string {
    return this.tierDrafts()[key] ?? '';
  }

  setDraft(key: string, value: string): void {
    this.tierDrafts.update((drafts) => ({ ...drafts, [key]: value }));
  }

  saveTierModel(key: string): void {
    this.savedMessage.set('');
    this.savingKey.set(key);
    const value = this.draftFor(key).trim();
    this.api.updateTierModel(key, { generation_model: value || null }).subscribe({
      next: () => {
        this.savingKey.set(null);
        this.savedMessage.set(`Saved ${key}.`);
        this.load();
      },
      error: () => {
        this.savingKey.set(null);
        this.errorMessage.set(`Failed to save ${key}.`);
      },
    });
  }

  toggleTierActive(tier: AdminTierModelRow): void {
    this.savedMessage.set('');
    this.errorMessage.set('');
    this.togglingKey.set(tier.key);
    this.api.setTierActive(tier.key, { is_active: !tier.is_active }).subscribe({
      next: () => {
        this.togglingKey.set(null);
        this.savedMessage.set(`${tier.label} is now ${tier.is_active ? 'disabled' : 'active'}.`);
        this.load();
      },
      error: () => {
        this.togglingKey.set(null);
        this.errorMessage.set(`Failed to update ${tier.label}.`);
      },
    });
  }

  saveVisionModel(): void {
    const value = this.visionDraft().trim();
    if (!value) {
      this.errorMessage.set('Vision model cannot be empty.');
      return;
    }
    this.errorMessage.set('');
    this.savedMessage.set('');
    this.savingVision.set(true);
    this.api.updateVisionModel({ model_name: value }).subscribe({
      next: (res) => {
        this.savingVision.set(false);
        this.visionModel.set(res);
        this.savedMessage.set('Saved vision model.');
      },
      error: () => {
        this.savingVision.set(false);
        this.errorMessage.set('Failed to save vision model.');
      },
    });
  }

  private load(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.api.listTierModels().subscribe({
      next: (res) => {
        this.tiers.set(res.items);
        const drafts: Record<string, string> = {};
        for (const tier of res.items) {
          drafts[tier.key] = tier.generation_model ?? '';
        }
        this.tierDrafts.set(drafts);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load tier models.');
        this.loading.set(false);
      },
    });
    this.api.getVisionModel().subscribe({
      next: (res) => {
        this.visionModel.set(res);
        this.visionDraft.set(res.model_name ?? '');
      },
    });
  }
}
