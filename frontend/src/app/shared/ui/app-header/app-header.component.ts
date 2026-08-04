import { Component, ElementRef, HostListener, effect, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from '../../../core/auth.service';
import { RedoWebsApiService } from '../../../core/redowebs-api.service';
import { BadgeComponent } from '../badge/badge.component';
import { IconChevronDown } from '../icons/icons';

/** Shared header for the authenticated pages (/app, /history) -- brand,
 * nav links, credit balance, avatar dropdown (profile + sign out). Not used
 * on the public welcome page, which has no session yet. */
@Component({
  selector: 'app-header',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, BadgeComponent, IconChevronDown],
  template: `
    <header class="sticky top-0 z-30 border-b border-white/6 bg-canvas/85 backdrop-blur-md">
      <div class="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <a routerLink="/app" class="flex items-center gap-2.5">
          <div
            class="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-teal text-sm font-bold text-white shadow-cta-glow"
          >
            R
          </div>
          <span class="text-lg font-bold tracking-tight text-ink">ReDoWebs</span>
        </a>

        <nav class="hidden items-center gap-1 rounded-full border border-white/6 bg-white/5 p-1 text-sm font-medium sm:flex">
          <a
            routerLink="/app"
            routerLinkActive="bg-accent/15 text-ink"
            [routerLinkActiveOptions]="{ exact: true }"
            class="rounded-full px-4 py-1.5 text-ink-muted transition-colors duration-200 hover:text-ink"
          >
            Home
          </a>
          <a
            routerLink="/history"
            routerLinkActive="bg-accent/15 text-ink"
            class="rounded-full px-4 py-1.5 text-ink-muted transition-colors duration-200 hover:text-ink"
          >
            History
          </a>
        </nav>

        <div class="flex items-center gap-3">
          @if (balance(); as b) {
            <app-badge [variant]="b <= 1 ? 'danger' : 'accent'">{{ b }} credit{{ b === 1 ? '' : 's' }}</app-badge>
          }

          <div class="relative">
            <button
              type="button"
              (click)="toggleMenu($event)"
              class="flex items-center gap-1.5 rounded-full py-1 pl-1 pr-2 transition-colors duration-200 hover:bg-white/5"
            >
              <span
                class="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-magenta text-sm font-semibold text-white"
              >
                {{ initial() }}
              </span>
              <app-icon-chevron-down [size]="16" class="text-ink-muted" />
            </button>

            @if (menuOpen()) {
              <div
                class="animate-fade-up absolute right-0 top-full mt-2 w-56 rounded-[10px] border border-border-card bg-canvas-elevated py-2 shadow-card"
                style="--fade-delay: 0s"
              >
                <p class="truncate px-4 py-2 text-sm text-ink-muted">{{ auth.currentUser()?.email }}</p>
                <div class="my-1 border-t border-white/6"></div>
                <a
                  routerLink="/history"
                  (click)="closeMenu()"
                  class="block px-4 py-2 text-sm text-ink transition-colors duration-200 hover:bg-white/5"
                >
                  My Generations
                </a>
                <div class="my-1 border-t border-white/6"></div>
                <button
                  type="button"
                  (click)="signOut()"
                  class="block w-full px-4 py-2 text-left text-sm font-medium text-red-400 transition-colors duration-200 hover:bg-red-500/10"
                >
                  Sign Out
                </button>
              </div>
            }
          </div>
        </div>
      </div>
    </header>
  `,
})
export class AppHeaderComponent {
  readonly balance = signal<number | null>(null);
  readonly menuOpen = signal(false);

  private readonly elementRef = inject(ElementRef<HTMLElement>);

  constructor(
    readonly auth: AuthService,
    private readonly api: RedoWebsApiService,
    private readonly router: Router
  ) {
    effect(() => {
      if (this.auth.isAuthenticated()) {
        this.api.getWallet().subscribe((wallet) => this.balance.set(wallet.balance));
      }
    });
  }

  initial(): string {
    return (this.auth.currentUser()?.email ?? '?').charAt(0).toUpperCase();
  }

  toggleMenu(event: MouseEvent): void {
    event.stopPropagation();
    this.menuOpen.set(!this.menuOpen());
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.menuOpen() && !this.elementRef.nativeElement.contains(event.target as Node)) {
      this.closeMenu();
    }
  }

  signOut(): void {
    this.closeMenu();
    this.auth.logout();
    this.router.navigate(['/']);
  }
}
