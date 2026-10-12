import { Injectable } from '@angular/core';

import { setTierLabels } from './project-status';
import { RedoWebsApiService } from './redowebs-api.service';

/** Loads tier display labels once (public GET /tiers) so tierLabel() shows
 * what admins named each tier rather than its raw key. Non-blocking: until
 * it answers, or if it fails, tierLabel() falls back to the capitalised
 * key. */
@Injectable({ providedIn: 'root' })
export class TierLabelService {
  private loaded = false;

  constructor(private readonly api: RedoWebsApiService) {}

  load(): void {
    if (this.loaded) {
      return;
    }
    this.loaded = true;
    this.api.getTiers().subscribe({
      next: (res) => setTierLabels(Object.fromEntries(res.items.map((t) => [t.key, t.label]))),
      error: () => {
        this.loaded = false;
      },
    });
  }
}
