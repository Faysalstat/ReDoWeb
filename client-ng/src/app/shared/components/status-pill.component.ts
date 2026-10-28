import { Component, computed, input } from '@angular/core';
import { Loader2, LucideAngularModule } from 'lucide-angular';

import { statusLabel } from '../../core/project-status';
import { BUSY_STATUSES, STATUS_PILL } from '../design/accents';

/** Blueprint §7.6 status pill for a raw backend Project.status. */
@Component({
  selector: 'app-status-pill',
  standalone: true,
  imports: [LucideAngularModule],
  template: `
    <span class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-medium" [class]="colors()">
      @if (busy()) {
        <lucide-icon [img]="Loader2" class="w-3 h-3 animate-spin" />
      }
      {{ label() }}
    </span>
  `,
})
export class StatusPillComponent {
  readonly status = input.required<string>();
  protected readonly Loader2 = Loader2;
  protected readonly colors = computed(() => STATUS_PILL[this.status()] ?? STATUS_PILL['pending']);
  protected readonly busy = computed(() => BUSY_STATUSES.has(this.status()));
  protected readonly label = computed(() => statusLabel(this.status()));
}
