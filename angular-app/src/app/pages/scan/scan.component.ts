import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AppNavComponent } from '../../shared/app-nav.component';
import { RefitService } from '../../core/refit.service';
import { ScanPhaseState } from '../../core/models';

@Component({
  selector: 'app-scan',
  standalone: true,
  imports: [RouterLink, AppNavComponent],
  templateUrl: './scan.component.html',
  styleUrl: './scan.component.scss',
})
export class ScanComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly refit = inject(RefitService);
  readonly id = this.route.snapshot.paramMap.get('id') ?? 'demo';
  readonly scan = toSignal(this.refit.scan(this.id));

  mark(state: ScanPhaseState): string {
    return state === 'waiting' ? 'var(--color-neutral-400)' : 'var(--color-accent)';
  }
  stateLabel(state: ScanPhaseState, detail?: string): string {
    if (state === 'running') return detail ?? 'Running';
    if (state === 'done') return 'Done';
    if (state === 'failed') return 'Failed';
    return 'Waiting';
  }
}
