import { Component } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../../../core/auth.service';

/** Layout shell for the whole /admin section: sidebar nav + topbar +
 * <router-outlet>. Deliberately not a reuse of AppHeaderComponent -- that's
 * a horizontal marketing-site header for the regular user flow, this is a
 * structurally different sidebar admin layout.
 *
 * Nav only lists pages that actually exist yet (Overview) -- more entries
 * get added here as Usage/Revenue/Users/Projects/Tiers are built in later
 * phases, rather than linking to routes that don't exist. */
@Component({
  selector: 'app-admin-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <div class="flex min-h-screen bg-canvas text-ink">
      <aside class="flex w-60 shrink-0 flex-col border-r border-white/6 bg-canvas-elevated-2 px-4 py-6">
        <a routerLink="/admin" class="mb-8 flex items-center gap-2.5 px-2">
          <div
            class="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-teal text-sm font-bold text-white"
          >
            R
          </div>
          <span class="text-base font-bold tracking-tight text-ink">Admin</span>
        </a>

        <nav class="flex flex-col gap-1 text-sm font-medium">
          <a
            routerLink="/admin/overview"
            routerLinkActive="bg-accent/15 text-ink"
            class="rounded-lg px-3 py-2 text-ink-muted transition-colors duration-200 hover:bg-white/5 hover:text-ink"
          >
            Overview
          </a>
        </nav>

        <div class="mt-auto flex flex-col gap-2 px-2 pt-6">
          <a routerLink="/app" class="text-xs text-ink-muted transition-colors duration-200 hover:text-ink">
            &larr; Back to app
          </a>
          <p class="truncate text-xs text-ink-faint">{{ auth.currentUser()?.email }}</p>
          <button
            type="button"
            (click)="signOut()"
            class="w-fit text-xs font-medium text-red-400 transition-colors duration-200 hover:text-red-300"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main class="min-w-0 flex-1 overflow-y-auto px-8 py-8">
        <router-outlet />
      </main>
    </div>
  `,
})
export class AdminShellComponent {
  constructor(
    readonly auth: AuthService,
    private readonly router: Router
  ) {}

  signOut(): void {
    this.auth.logout();
    this.router.navigate(['/']);
  }
}
