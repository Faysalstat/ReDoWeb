import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { isTerminal, stagePercent, statusBadgeVariant, statusLabel, tierLabel } from '../../core/project-status';
import { ProjectListItem } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { chipClass } from '../../ui/chip';
import { IconArrowRight, IconCheck, IconGlobe } from '../../ui/icons';

/** /history: every project the user has submitted, newest first, as a stack
 * of sticker cards. */
@Component({
  selector: 'pg-history',
  standalone: true,
  imports: [RouterLink, DatePipe, IconArrowRight, IconCheck, IconGlobe],
  template: `
    <div class="pg-wrap hs">
      <header class="hs__head">
        <div>
          <span class="pg-kicker">History</span>
          <h1 class="hs__title">My <span class="pg-squiggle">redesigns</span></h1>
          <p class="pg-muted">Every site you've submitted, newest first.</p>
        </div>
        <a class="pg-btn" routerLink="/">
          New redesign <span class="pg-btn__icon"><app-icon-arrow-right [size]="14" /></span>
        </a>
      </header>

      @if (loading()) {
        <div class="hs__list" aria-busy="true">
          @for (i of [0, 1, 2]; track i) {
            <div class="pg-card hs__skeleton"></div>
          }
        </div>
      } @else if (errorMessage()) {
        <p class="pg-err" role="alert">{{ errorMessage() }}</p>
      } @else if (projects().length === 0) {
        <div class="pg-card pg-card--featured hs__empty">
          <span class="pg-shape hs__dot" aria-hidden="true"></span>
          <span class="pg-shape hs__sq" aria-hidden="true"></span>
          <span class="pg-icon-badge pg-icon-badge--amber hs__empty-icon"><app-icon-globe [size]="28" /></span>
          <h2>No redesigns yet</h2>
          <p class="pg-muted">Paste a URL on the homepage to make your first one. The preview is free.</p>
          <a class="pg-btn" routerLink="/">Start a redesign</a>
        </div>
      } @else {
        <ul class="hs__list">
          @for (project of projects(); track project.project_id; let i = $index) {
            <li class="pg-card hs__row" [style.--c]="accents[i % accents.length]">
              <span class="hs__bar" aria-hidden="true"></span>
              <div class="hs__site">
                <p class="hs__domain" [title]="project.source_url">{{ host(project.source_url) }}</p>
                <p class="pg-muted hs__date">{{ project.created_at | date: 'medium' }}</p>
              </div>

              <div class="hs__status">
                <div class="hs__chips">
                  @if (project.tier) {
                    <span class="pg-chip pg-chip--accent">{{ tierLabel(project.tier) }}</span>
                  }
                  <span [class]="chip(project.status)">{{ statusLabel(project.status) }}</span>
                  @if (project.purchased_tiers.length > 0) {
                    <span class="pg-chip pg-chip--mint" title="Paid for. Re-downloading is free.">
                      <app-icon-check [size]="12" /> Paid{{ project.purchased_tiers.length > 1 ? ' · ' + paidLabels(project.purchased_tiers) : '' }}
                    </span>
                  }
                </div>
                @if (!isTerminal(project.status)) {
                  <div class="hs__progress">
                    <div class="pg-meter pg-meter--sm" role="progressbar" aria-label="Progress" aria-valuemin="0" aria-valuemax="100" [attr.aria-valuenow]="stagePercent(project.status)">
                      <span [style.width.%]="stagePercent(project.status)"></span>
                    </div>
                    <b>{{ stagePercent(project.status) }}%</b>
                  </div>
                }
              </div>

              <div class="hs__actions">
                @for (tier of project.purchased_tiers; track tier) {
                  <a class="pg-btn pg-btn--sm" [routerLink]="['/projects', project.project_id]" [queryParams]="{ download: tier }" [title]="'Download the ' + tierLabel(tier) + ' ZIP again (free)'">
                    Download{{ project.purchased_tiers.length > 1 ? ' ' + tierLabel(tier) : '' }}
                  </a>
                }
                <a class="pg-btn pg-btn--sm pg-btn--secondary" [routerLink]="['/projects', project.project_id]">
                  {{ isTerminal(project.status) ? 'View' : 'Watch progress' }}
                </a>
              </div>
            </li>
          }
        </ul>
      }
    </div>
  `,
  styles: [
    `
      .hs { padding-block: 48px 96px; display: grid; gap: 36px; }
      .hs__head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 20px; }
      .hs__head > div { display: grid; gap: 12px; justify-items: start; }
      .hs__title { font-size: clamp(2.2rem, 5vw, var(--pg-text-4xl)); }
      .hs__list { list-style: none; margin: 0; padding: 0; display: grid; gap: 18px; }
      .hs__skeleton { height: 92px; background: var(--pg-muted); box-shadow: none; animation: pg-pop-in 900ms ease infinite alternate; }
      .hs__row {
        /* Fixed status/actions tracks so every row lines up, whatever its buttons. */
        display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 280px) minmax(0, 430px); align-items: center; gap: 20px;
        padding: 18px 22px 18px 32px; overflow: hidden; transition: transform 300ms var(--pg-bounce), box-shadow 300ms var(--pg-bounce);
      }
      .hs__row:hover { transform: translate(-2px, -2px); box-shadow: 10px 10px 0 0 var(--c); }
      .hs__bar { position: absolute; left: 0; top: 0; bottom: 0; width: 12px; background: var(--c); border-right: var(--pg-bw) solid var(--pg-fg); }
      .hs__site { min-width: 0; }
      .hs__domain { font: 700 var(--pg-text-lg) / 1.25 var(--pg-font-heading); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .hs__date { font-size: var(--pg-text-xs); margin-top: 2px; }
      .hs__status { display: grid; gap: 10px; }
      .hs__chips { display: flex; flex-wrap: wrap; gap: 6px; }
      .hs__progress { display: flex; align-items: center; gap: 10px; font-size: var(--pg-text-xs); }
      .hs__progress .pg-meter { flex: 1; max-width: 220px; }
      .hs__actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; justify-self: end; }
      .hs__empty { position: relative; overflow: hidden; display: grid; justify-items: center; gap: 14px; text-align: center; padding: 64px 24px; }
      .hs__empty h2 { font-size: var(--pg-text-2xl); }
      .hs__empty-icon { --_size: 72px; }
      .hs__dot { width: 120px; height: 120px; border-radius: 50%; background: var(--pg-pink-soft); border: 2px solid var(--pg-fg); top: -40px; left: -30px; }
      .hs__sq { width: 70px; height: 70px; background: var(--pg-mint-soft); border: 2px solid var(--pg-fg); border-radius: 14px; bottom: -20px; right: 30px; transform: rotate(18deg); }
      @media (max-width: 1100px) {
        .hs__row { grid-template-columns: minmax(0, 1fr) minmax(0, 260px); }
        .hs__actions { grid-column: 1 / -1; }
      }
      @media (max-width: 880px) {
        .hs__row { grid-template-columns: 1fr; gap: 14px; }
        .hs__actions { justify-content: flex-start; justify-self: start; }
      }
    `,
  ],
})
export class HistoryComponent implements OnInit {
  private readonly api = inject(RedoWebsApiService);

  readonly projects = signal<ProjectListItem[]>([]);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  readonly statusLabel = statusLabel;
  readonly stagePercent = stagePercent;
  readonly isTerminal = isTerminal;
  readonly tierLabel = tierLabel;
  readonly accents = ['var(--pg-accent)', 'var(--pg-pink)', 'var(--pg-amber)', 'var(--pg-mint)'];

  ngOnInit(): void {
    this.api.listProjects().subscribe({
      next: (projects) => {
        this.projects.set(projects);
        this.loading.set(false);
      },
      error: (err: HttpErrorResponse) => {
        const detail = err.error?.detail;
        this.errorMessage.set(typeof detail === 'string' ? detail : 'Could not load your redesigns.');
        this.loading.set(false);
      },
    });
  }

  chip(status: string): string {
    return chipClass(statusBadgeVariant(status));
  }

  /** "Premium, Pro" -- only shown when more than one tier is paid for. */
  paidLabels(tiers: string[]): string {
    return tiers.map(tierLabel).join(', ');
  }

  /** Domain only; the full URL stays in the title tooltip. */
  host(url: string): string {
    try {
      return new URL(url).host || url;
    } catch {
      return url;
    }
  }
}
