import { DOCUMENT } from '@angular/common';
import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter, map } from 'rxjs';

import { PgFooterComponent } from './layout/pg-footer.component';
import { PgHeaderComponent } from './layout/pg-header.component';

/** App root. The `.pg` wrapper is the scope every design-system rule in
 * styles.css hangs off. */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet, PgHeaderComponent, PgFooterComponent],
  template: `
    <div class="pg">
      <a class="pg-skip" href="#pg-main" (click)="skipToMain($event)">Skip to content</a>
      <pg-header />
      <main id="pg-main" class="pg-main" tabindex="-1">
        <router-outlet />
      </main>
      @if (!inAdmin()) {
        <pg-footer />
      }
    </div>
  `,
  styles: [
    `
      .pg-skip {
        position: absolute;
        left: 16px;
        top: -60px;
        z-index: 100;
        padding: 10px 16px;
        border: var(--pg-bw) solid var(--pg-fg);
        border-radius: var(--pg-radius-full);
        background: var(--pg-amber);
        color: var(--pg-fg);
        box-shadow: var(--pg-pop);
      }
      .pg-skip:focus {
        top: 12px;
      }
      .pg-main:focus {
        outline: none;
      }
    `,
  ],
})
export class App {
  private readonly document = inject(DOCUMENT);
  private readonly router = inject(Router);

  /** The admin section has its own sidebar shell, so the site footer is hidden there. */
  readonly inAdmin = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map((e) => e.urlAfterRedirects.startsWith('/admin'))
    ),
    { initialValue: false }
  );

  /** A plain href="#…" resolves against <base href="/">, which would reload
   * the homepage from any other route. */
  skipToMain(event: Event): void {
    event.preventDefault();
    this.document.getElementById('pg-main')?.focus();
  }
}
