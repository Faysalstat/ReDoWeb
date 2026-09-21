import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminUserListItem } from '../core/admin-api.models';

const PAGE_SIZE = 25;

@Component({
  selector: 'app-admin-users-list',
  standalone: true,
  imports: [RouterLink, DatePipe, SpinnerComponent, ButtonComponent],
  templateUrl: './admin-users-list.component.html',
})
export class AdminUsersListComponent implements OnInit {
  readonly users = signal<AdminUserListItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly search = signal('');
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  readonly pageSize = PAGE_SIZE;

  constructor(private readonly api: AdminApiService) {}

  ngOnInit(): void {
    this.load();
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
    this.api.listUsers({ search: this.search() || undefined, page: this.page(), pageSize: this.pageSize }).subscribe({
      next: (res) => {
        this.users.set(res.items);
        this.total.set(res.total);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load users.');
        this.loading.set(false);
      },
    });
  }
}
