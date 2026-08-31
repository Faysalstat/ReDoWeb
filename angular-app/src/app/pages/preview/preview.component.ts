import { Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { SiteMockComponent } from '../../shared/site-mock.component';
import { RefitService } from '../../core/refit.service';

type CompareMode = 'split' | 'wipe';
type Device = 'desktop' | 'phone';

@Component({
  selector: 'app-preview',
  standalone: true,
  imports: [FormsModule, RouterLink, SiteMockComponent],
  templateUrl: './preview.component.html',
  styleUrl: './preview.component.scss',
})
export class PreviewComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly refit = inject(RefitService);
  readonly id = this.route.snapshot.paramMap.get('id') ?? 'demo';

  readonly scores = toSignal(this.refit.previewScores(this.id));
  readonly pages = toSignal(this.refit.previewPages(this.id), { initialValue: [] as string[] });

  readonly mode = signal<CompareMode>('split');
  readonly device = signal<Device>('desktop');
  wipe = 46;
  page = 'Home';

  get frameWidth(): number { return this.device() === 'phone' ? 320 : 480; }
}
