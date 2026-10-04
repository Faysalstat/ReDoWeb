import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { BadgeComponent, BadgeVariant } from '../../../shared/ui/badge/badge.component';
import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminProjectListItem } from '../core/admin-api.models';

const PAGE_SIZE = 25;

const TIER_BADGE_VARIANT: Record<string, BadgeVariant> = {
  basic: 'muted',
  premium: 'warning',
  pro: 'accent',
};

/** Cross-user project browse -- supports a `?user_id=` query param so the
 * Users detail page's "view this user's projects" link can deep-link in
 * pre-filtered, sharing this page instead of duplicating a table. */
@Component({
  selector: 'app-admin-projects-list',
  standalone: true,
  imports: [RouterLink, DatePipe, SpinnerComponent, ButtonComponent, BadgeComponent],
  templateUrl: './admin-projects-list.component.html',
})
export class AdminProjectsListComponent implements OnInit {
  readonly projects = signal<AdminProjectListItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly search = signal('');
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  readonly pageSize = PAGE_SIZE;

  private userId: string | undefined;

  constructor(
    private readonly route: ActivatedRoute,
    private readonly api: AdminApiService
  ) {}

  ngOnInit(): void {
    this.userId = this.route.snapshot.queryParamMap.get('user_id') ?? undefined;
    this.load();
  }

  tierBadgeVariant(tier: string | null): BadgeVariant {
    return tier ? (TIER_BADGE_VARIANT[tier] ?? 'muted') : 'muted';
  }

  onSearchChange(value: string): void {
    this.search.set(value);
    this.page.set(1);
    this.load();
  }

  nextPage(): void {
    if (this.page() * this.pageSize >= this.total()) return;
    this.page.update((p) => p + 1);
    this.load();
  }

  prevPage(): void {
    if (this.page() <= 1) return;
    this.page.update((p) => p - 1);
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.api
      .listProjects({ search: this.search() || undefined, userId: this.userId, page: this.page(), pageSize: this.pageSize })
      .subscribe({
        next: (res) => {
          this.projects.set(res.items);
          this.total.set(res.total);
          this.loading.set(false);
        },
        error: () => {
          this.errorMessage.set('Failed to load projects.');
          this.loading.set(false);
        },
      });
  }
}
