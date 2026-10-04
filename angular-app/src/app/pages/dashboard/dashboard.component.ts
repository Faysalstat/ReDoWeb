import { Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AppNavComponent } from '../../shared/app-nav.component';
import { RefitService } from '../../core/refit.service';
import { Site, SiteStatus } from '../../core/models';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [FormsModule, RouterLink, AppNavComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  private readonly refit = inject(RefitService);
  private readonly all = toSignal(this.refit.sites(), { initialValue: [] as Site[] });

  readonly density = signal<'roomy' | 'dense'>('roomy');
  filter = '';

  readonly summary = [
    { value: '3', label: 'Sites live', accent: false },
    { value: '1', label: 'Awaiting your review', accent: true },
    { value: '1,284', label: 'Visitors, last 7 days', accent: false },
    { value: '$49', label: 'Next charge, 12 Sep', accent: false },
  ];

  sites(): Site[] {
    const q = this.filter.trim().toLowerCase();
    return q ? this.all().filter((s) => s.domain.toLowerCase().includes(q)) : this.all();
  }

  tag(status: SiteStatus): string {
    if (status === 'Rebuilding') return 'tag-accent';
    if (status === 'Your review') return 'tag-outline';
    return 'tag-neutral';
  }
}
