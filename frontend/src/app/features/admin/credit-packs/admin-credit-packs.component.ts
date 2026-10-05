import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { BadgeComponent } from '../../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminCreditPackRow } from '../core/admin-api.models';

interface PackDraft {
  name: string;
  credits: number;
  priceUsd: number;
  sortOrder: number;
}

/** PayPal's fixed fee is roughly $0.49 + ~3.5% per payment -- below this a
 * pack mostly pays PayPal, so the form warns (but doesn't block). */
const SMALL_PACK_WARNING_CENTS = 500;

/** Admin CRUD for the credit packs sold at /checkout (PayPal). Each pack
 * carries its own price, so bigger packs can be discounted. Packs are
 * disabled rather than deleted -- past purchases reference them, and an
 * order already in flight keeps the price it was created with. */
@Component({
  selector: 'app-admin-credit-packs',
  standalone: true,
  imports: [FormsModule, DatePipe, BadgeComponent, ButtonComponent, SpinnerComponent],
  templateUrl: './admin-credit-packs.component.html',
})
export class AdminCreditPacksComponent implements OnInit {
  readonly packs = signal<AdminCreditPackRow[]>([]);
  readonly loading = signal(true);
  readonly errorMessage = signal('');
  readonly savedMessage = signal('');
  readonly busyId = signal<string | null>(null);
  readonly drafts = signal<Record<string, PackDraft>>({});
  newPack: PackDraft & { isActive: boolean } = { name: '', credits: 10, priceUsd: 10, sortOrder: 0, isActive: false };

  constructor(private readonly api: AdminApiService) {}

  ngOnInit(): void {
    this.load();
  }

  draft(id: string): PackDraft {
    return this.drafts()[id];
  }

  updateDraft(id: string, field: keyof PackDraft, value: string | number): void {
    const current = this.drafts()[id];
    this.drafts.set({ ...this.drafts(), [id]: { ...current, [field]: field === 'name' ? value : Number(value) } });
  }

  perCredit(priceUsd: number, credits: number): string {
    return credits > 0 ? `$${(priceUsd / credits).toFixed(2)}` : '—';
  }

  isSmall(priceUsd: number): boolean {
    return Math.round(priceUsd * 100) < SMALL_PACK_WARNING_CENTS;
  }

  create(): void {
    const body = this.toBody(this.newPack);
    if (!body) return;
    this.begin('new');
    this.api.createCreditPack({ ...body, is_active: this.newPack.isActive }).subscribe({
      next: (pack) => {
        this.done(`Created "${pack.name}".`);
        this.newPack = { name: '', credits: 10, priceUsd: 10, sortOrder: 0, isActive: false };
      },
      error: (err) => this.failed(err, 'create the pack'),
    });
  }

  save(pack: AdminCreditPackRow): void {
    const body = this.toBody(this.draft(pack.id));
    if (!body) return;
    this.begin(pack.id);
    this.api.updateCreditPack(pack.id, body).subscribe({
      next: (row) => this.done(`Saved "${row.name}".`),
      error: (err) => this.failed(err, `save "${pack.name}"`),
    });
  }

  toggleActive(pack: AdminCreditPackRow): void {
    this.begin(pack.id);
    this.api.setCreditPackActive(pack.id, !pack.is_active).subscribe({
      next: (row) => this.done(`"${row.name}" is now ${row.is_active ? 'on sale' : 'hidden'}.`),
      error: (err) => this.failed(err, `update "${pack.name}"`),
    });
  }

  private toBody(d: PackDraft): { name: string; credits: number; price_usd_cents: number; sort_order: number } | null {
    const name = d.name.trim();
    const credits = Math.floor(d.credits);
    const cents = Math.round(d.priceUsd * 100);
    if (!name || credits < 1 || cents < 1) {
      this.errorMessage.set('Each pack needs a name, at least 1 credit, and a price above $0.');
      return null;
    }
    return { name, credits, price_usd_cents: cents, sort_order: Math.floor(d.sortOrder) || 0 };
  }

  private begin(id: string): void {
    this.errorMessage.set('');
    this.savedMessage.set('');
    this.busyId.set(id);
  }

  private done(message: string): void {
    this.busyId.set(null);
    this.savedMessage.set(message);
    this.load();
  }

  private failed(err: HttpErrorResponse, action: string): void {
    this.busyId.set(null);
    const detail = err.error?.detail;
    this.errorMessage.set(typeof detail === 'string' ? detail : `Failed to ${action}.`);
  }

  private load(): void {
    this.loading.set(true);
    this.api.listCreditPacks().subscribe({
      next: (res) => {
        this.packs.set(res.items);
        const drafts: Record<string, PackDraft> = {};
        for (const p of res.items) {
          drafts[p.id] = { name: p.name, credits: p.credits, priceUsd: p.price_usd_cents / 100, sortOrder: p.sort_order };
        }
        this.drafts.set(drafts);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load credit packs.');
        this.loading.set(false);
      },
    });
  }
}
