import { Component, ElementRef, HostListener, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from '../core/auth.service';
import { WalletService } from '../core/wallet.service';
import { IconChevronDown } from '../ui/icons';
import { PgLogoComponent } from './pg-logo.component';

/** Site header: brand, nav, and either the credit balance + account menu
 * (signed in) or a "Log in" button (signed out). */
@Component({
  selector: 'pg-header',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, IconChevronDown, PgLogoComponent],
  template: `
    <header class="pgh">
      <div class="pg-wrap pgh__bar">
        <a routerLink="/" class="pgh__brand" aria-label="ReDoWebs home"><pg-logo /></a>

        <nav class="pgh__nav" aria-label="Main">
          <a routerLink="/" routerLinkActive="is-active" [routerLinkActiveOptions]="{ exact: true }" ariaCurrentWhenActive="page">Home</a>
          <a routerLink="/pricing" routerLinkActive="is-active" ariaCurrentWhenActive="page">Pricing</a>
          @if (auth.isAuthenticated()) {
            <a routerLink="/history" routerLinkActive="is-active" ariaCurrentWhenActive="page">History</a>
            <a routerLink="/settings/billing" routerLinkActive="is-active" ariaCurrentWhenActive="page">Billing</a>
          }
        </nav>

        <div class="pgh__right">
          @if (auth.isAuthenticated()) {
            @if (wallet.balance() !== null) {
              @let b = wallet.balance()!;
              <a routerLink="/checkout" class="pgh__credits" [class.is-low]="b <= 1" title="Buy credits">
                <span class="pgh__coin" aria-hidden="true"></span>
                {{ b }} credit{{ b === 1 ? '' : 's' }}
              </a>
            }

            <div class="pgh__menu">
              <button type="button" class="pgh__avatar-btn" (click)="toggleMenu($event)" [attr.aria-expanded]="menuOpen()" aria-haspopup="menu">
                <span class="pgh__avatar">{{ initial() }}</span>
                <app-icon-chevron-down [size]="16" />
                <span class="pg-sr-only">Account menu</span>
              </button>
              @if (menuOpen()) {
                <div class="pgh__dropdown pg-pop-in" role="menu">
                  <p class="pgh__email">{{ auth.currentUser()?.email }}</p>
                  <a routerLink="/history" role="menuitem" (click)="closeMenu()">My generations</a>
                  <a routerLink="/settings/billing" role="menuitem" (click)="closeMenu()">Billing</a>
                  @if (auth.currentUser()?.is_admin) {
                    <a routerLink="/admin" role="menuitem" (click)="closeMenu()">Admin</a>
                  }
                  <button type="button" role="menuitem" (click)="signOut()">Sign out</button>
                </div>
              }
            </div>
          } @else {
            <a class="pg-btn pg-btn--sm" routerLink="/login">Log in</a>
          }
        </div>
      </div>
    </header>
  `,
  styles: [
    `
      .pgh {
        position: sticky;
        top: 0;
        z-index: 50;
        background: color-mix(in srgb, var(--pg-bg) 92%, transparent);
        backdrop-filter: blur(8px);
        border-bottom: var(--pg-bw) solid var(--pg-fg);
      }
      .pgh__bar {
        display: flex;
        align-items: center;
        gap: 28px;
        min-height: 72px;
      }
      .pgh__brand {
        text-decoration: none;
        flex: none;
      }
      .pgh__nav {
        display: flex;
        gap: 6px;
      }
      .pgh__nav a {
        padding: 8px 14px;
        border-radius: var(--pg-radius-full);
        border: var(--pg-bw) solid transparent;
        color: var(--pg-fg);
        font-weight: 700;
        font-size: var(--pg-text-sm);
        text-decoration: none;
        transition: background-color 150ms ease;
      }
      .pgh__nav a:hover {
        background: var(--pg-muted);
      }
      .pgh__nav a.is-active {
        border-color: var(--pg-fg);
        background: var(--pg-amber);
      }
      .pgh__right {
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .pgh__credits {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px 6px 8px;
        border: var(--pg-bw) solid var(--pg-fg);
        border-radius: var(--pg-radius-full);
        background: var(--pg-mint-soft);
        color: var(--pg-fg);
        font-weight: 800;
        font-size: var(--pg-text-sm);
        text-decoration: none;
        box-shadow: var(--pg-pop-active);
      }
      .pgh__credits.is-low {
        background: var(--pg-pink-soft);
      }
      .pgh__coin {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: var(--pg-amber);
        border: var(--pg-bw) solid var(--pg-fg);
      }
      .pgh__menu {
        position: relative;
      }
      .pgh__avatar-btn {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 0;
        border: 0;
        background: transparent;
        color: var(--pg-fg);
        cursor: pointer;
      }
      .pgh__avatar {
        display: grid;
        place-items: center;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: var(--pg-accent);
        color: #fff;
        border: var(--pg-bw) solid var(--pg-fg);
        font: 800 1rem/1 var(--pg-font-heading);
      }
      .pgh__dropdown {
        position: absolute;
        right: 0;
        top: calc(100% + 10px);
        min-width: 220px;
        display: grid;
        padding: 8px;
        background: var(--pg-card);
        border: var(--pg-bw) solid var(--pg-fg);
        border-radius: var(--pg-radius-md);
        box-shadow: var(--pg-pop);
        transform-origin: top right;
      }
      .pgh__email {
        padding: 8px 10px 10px;
        margin-bottom: 4px;
        border-bottom: var(--pg-bw) dashed var(--pg-border);
        font-size: var(--pg-text-xs);
        color: var(--pg-muted-fg);
        overflow-wrap: anywhere;
      }
      .pgh__dropdown a,
      .pgh__dropdown button {
        display: block;
        width: 100%;
        padding: 10px;
        border: 0;
        border-radius: var(--pg-radius-sm);
        background: transparent;
        color: var(--pg-fg);
        font: 600 var(--pg-text-sm) / 1.2 var(--pg-font-body);
        text-align: left;
        text-decoration: none;
        cursor: pointer;
      }
      .pgh__dropdown a:hover,
      .pgh__dropdown button:hover {
        background: var(--pg-amber-soft);
      }
      @media (max-width: 880px) {
        .pgh__bar {
          flex-wrap: wrap;
          row-gap: 0;
        }
        .pgh__nav {
          order: 3;
          width: 100%;
          overflow-x: auto;
          padding: 2px 0 12px;
          scrollbar-width: none;
        }
        .pgh__nav a {
          flex: none;
        }
      }
      @media (max-width: 520px) {
        .pgh__bar {
          gap: 12px;
        }
      }
    `,
  ],
})
export class PgHeaderComponent {
  readonly auth = inject(AuthService);
  readonly wallet = inject(WalletService);
  readonly menuOpen = signal(false);
  private readonly router = inject(Router);
  private readonly elementRef = inject(ElementRef<HTMLElement>);

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

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.closeMenu();
  }

  signOut(): void {
    this.closeMenu();
    this.auth.logout();
    this.router.navigate(['/']);
  }
}
