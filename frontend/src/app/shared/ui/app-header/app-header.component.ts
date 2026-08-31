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
    <header class="nav">
      <a routerLink="/app" class="nav-brand">ReDoWebs</a>

      <a routerLink="/app" ariaCurrentWhenActive="page" [routerLinkActiveOptions]="{ exact: true }" routerLinkActive>Home</a>
      <a routerLink="/history" ariaCurrentWhenActive="page" routerLinkActive>History</a>
      <a routerLink="/settings/billing" ariaCurrentWhenActive="page" routerLinkActive>Billing</a>

      @if (balance(); as b) {
        <app-badge [variant]="b <= 1 ? 'danger' : 'accent'">{{ b }} credit{{ b === 1 ? '' : 's' }}</app-badge>
      }

      <div class="app-header__menu">
        <button type="button" (click)="toggleMenu($event)" class="app-header__avatar-btn">
          <span class="app-header__avatar">{{ initial() }}</span>
          <app-icon-chevron-down [size]="16" />
        </button>

        @if (menuOpen()) {
          <div class="app-header__dropdown">
            <p class="app-header__email">{{ auth.currentUser()?.email }}</p>
            <hr class="hr" />
            <a routerLink="/history" (click)="closeMenu()">My Generations</a>
            <hr class="hr" />
            <button type="button" (click)="signOut()" class="app-header__signout">Sign Out</button>
          </div>
        }
      </div>
    </header>
  `,
  styles: [
    `
      .app-header__menu {
        position: relative;
        margin-left: var(--space-2);
      }
      .app-header__avatar-btn {
        display: flex;
        align-items: center;
        gap: 6px;
        background: transparent;
        border: none;
        cursor: pointer;
        color: var(--color-text);
        padding: 4px;
      }
      .app-header__avatar {
        display: flex;
        height: 32px;
        width: 32px;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        background: var(--color-accent);
        color: var(--color-bg);
        font-size: 13px;
        font-weight: 700;
      }
      .app-header__dropdown {
        position: absolute;
        right: 0;
        top: calc(100% + 8px);
        width: 220px;
        background: var(--color-surface);
        border: 2px solid var(--color-divider);
        box-shadow: var(--shadow-md);
        padding: var(--space-3);
        display: flex;
        flex-direction: column;
        z-index: 30;
      }
      .app-header__email {
        margin: 0 0 var(--space-2);
        font-size: 12px;
        color: var(--color-neutral-700);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .app-header__dropdown a {
        padding: var(--space-2) 0;
      }
      .app-header__signout {
        text-align: left;
        background: transparent;
        border: none;
        cursor: pointer;
        padding: var(--space-2) 0 0;
        font-size: 14px;
        color: var(--color-accent-700);
        font-family: var(--font-body);
      }
    `,
  ],
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
