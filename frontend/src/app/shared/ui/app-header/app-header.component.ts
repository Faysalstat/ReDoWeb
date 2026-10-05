import { Component, ElementRef, HostListener, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from '../../../core/auth.service';
import { WalletService } from '../../../core/wallet.service';
import { BadgeComponent } from '../badge/badge.component';
import { ButtonComponent } from '../button/button.component';
import { IconChevronDown } from '../icons/icons';

/** Shared header for every page, public or authenticated -- brand, nav
 * links, and on the right either a credit balance + avatar dropdown (signed
 * in) or a single "Log in" button (signed out). */
@Component({
  selector: 'app-header',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, BadgeComponent, ButtonComponent, IconChevronDown],
  template: `
    <header class="nav">
      <a routerLink="/" class="nav-brand app-header__brand">
        <span class="app-header__mark">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M4 12h16M4 12l6-6M4 12l6 6" stroke="var(--color-bg)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        ReDoWebs
      </a>

      <a routerLink="/" ariaCurrentWhenActive="page" [routerLinkActiveOptions]="{ exact: true }" routerLinkActive>Home</a>

      @if (auth.isAuthenticated()) {
        <a routerLink="/history" ariaCurrentWhenActive="page" routerLinkActive>History</a>
        <a routerLink="/settings/billing" ariaCurrentWhenActive="page" routerLinkActive>Billing</a>

        @if (wallet.balance() !== null) {
          @let b = wallet.balance()!;
          <a routerLink="/checkout" title="Buy credits" class="app-header__balance">
            <app-badge [variant]="b <= 1 ? 'danger' : 'accent'">{{ b }} credit{{ b === 1 ? '' : 's' }}</app-badge>
          </a>
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
      } @else {
        <a appButton variant="primary" routerLink="/login" class="app-header__login">Log in</a>
      }
    </header>
  `,
  styles: [
    `
      .app-header__brand {
        display: inline-flex;
        align-items: center;
        gap: 10px;
      }
      .app-header__mark {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        border-radius: 7px;
        background: linear-gradient(135deg, var(--color-accent), var(--color-accent-2));
      }
      .app-header__menu {
        position: relative;
        margin-left: var(--space-2);
      }
      .app-header__login {
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
      .app-header__balance {
        text-decoration: none;
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
  readonly menuOpen = signal(false);

  private readonly elementRef = inject(ElementRef<HTMLElement>);

  constructor(
    readonly auth: AuthService,
    readonly wallet: WalletService,
    private readonly router: Router
  ) {}

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
