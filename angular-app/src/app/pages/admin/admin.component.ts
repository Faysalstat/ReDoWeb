import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { RefitService } from '../../core/refit.service';
import { Job } from '../../core/models';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.scss',
})
export class AdminComponent {
  private readonly refit = inject(RefitService);
  readonly data = toSignal(this.refit.adminOverview());

  jobTag(state: Job['state']): string {
    if (state === 'Running') return 'tag tag-accent';
    if (state === 'Retry') return 'tag tag-outline';
    return 'tag tag-neutral';
  }

  barHeight(value: number): number {
    const max = Math.max(...(this.data()?.revenueSeries.map((r) => r.value) ?? [1]));
    return Math.round((value / max) * 100);
  }
}
