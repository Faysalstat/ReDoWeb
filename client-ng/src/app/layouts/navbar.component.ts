import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { ArrowRight, Coins, LucideAngularModule, Menu, Shield, X } from 'lucide-angular';
import { filter, map } from 'rxjs';

import { AuthService } from '../core/auth.service';
import { WalletService } from '../core/wallet.service';
import { readLastProjectId } from '../shared/design/last-project';
import { LogoComponent } from '../shared/components/logo.component';
import { UiButton } from '../shared/ui/button.directive';

/** Blueprint §6.3 navbar. Only links to pages that exist; "View My Redesign"
 * reopens the last project submitted from this browser. */
@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, LucideAngularModule, LogoComponent, UiButton],
  template: `
    <nav class="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/90 backdrop-blur-xl">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <a routerLink="/" class="flex items-center shrink-0" aria-label="ReDoWebs home"><app-logo size="md" /></a>

          <div class="hidden lg:flex items-center gap-8">
            <a routerLink="/" fragment="hero" class="text-sm text-foreground hover:text-foreground/80 transition-colors">Redesign My Site</a>
            <a routerLink="/" fragment="how-it-works" class="text-sm text-foreground hover:text-foreground/80 transition-colors">How It Works</a>
            <a routerLink="/pricing" routerLinkActive="!text-primary" class="text-sm text-foreground hover:text-foreground/80 transition-colors">Pricing</a>
            @if (auth.isAuthenticated()) {
              <a routerLink="/history" routerLinkActive="!text-primary" class="text-sm text-foreground hover:text-foreground/80 transition-colors">History</a>
              <a routerLink="/settings/billing" routerLinkActive="!text-primary" class="text-sm text-foreground hover:text-foreground/80 transition-colors">Billing</a>
            }
          </div>

          <div class="hidden lg:flex items-center gap-3">
            @if (lastProjectId() && !onProject()) {
              <a
                uiButton
                size="sm"
                variant="outline"
                [routerLink]="['/projects', lastProjectId()]"
                class="gap-1 border-primary/40 text-foreground hover:bg-primary/10 hover:text-foreground"
              >
                View My Redesign <lucide-icon [img]="icons.ArrowRight" class="w-3 h-3" />
              </a>
            }
            @if (auth.isAuthenticated()) {
              @if (wallet.balance() !== null) {
                @let b = wallet.balance()!;
                <a
                  routerLink="/checkout"
                  title="Buy credits"
                  class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-semibold transition-colors"
                  [class]="b <= 1 ? 'border-red-500/30 bg-red-500/10 text-red-400 hover:bg-red-500/20' : 'border-primary/30 bg-primary/10 text-primary hover:bg-primary/20'"
                >
                  <lucide-icon [img]="icons.Coins" class="w-3.5 h-3.5" /> {{ b }} credit{{ b === 1 ? '' : 's' }}
                </a>
              }
              @if (auth.currentUser()?.is_admin) {
                <a uiButton variant="ghost" size="sm" routerLink="/admin" class="gap-1 text-foreground hover:bg-muted hover:text-foreground">
                  <lucide-icon [img]="icons.Shield" class="w-3.5 h-3.5" /> Admin
                </a>
              }
              <a uiButton size="sm" routerLink="/history" class="hover:bg-primary/85 text-white">Dashboard</a>
            } @else {
              <a uiButton variant="ghost" size="sm" routerLink="/login" class="text-foreground hover:text-foreground hover:bg-muted">Sign In</a>
              <a uiButton size="sm" routerLink="/login" class="bg-primary hover:bg-primary/90 text-white">Get Started</a>
            }
          </div>

          <button
            type="button"
            class="lg:hidden text-foreground p-1"
            (click)="open.set(!open())"
            [attr.aria-expanded]="open()"
            aria-label="Menu"
          >
            <lucide-icon [img]="open() ? icons.X : icons.Menu" class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- Mobile menu -->
      <div
        class="lg:hidden grid transition-all duration-200"
        [class]="open() ? 'grid-rows-[1fr] opacity-100 border-t border-border/50' : 'grid-rows-[0fr] opacity-0 pointer-events-none'"
      >
        <div class="overflow-hidden bg-background/95 backdrop-blur-xl">
          <div class="px-4 py-4 space-y-3" (click)="open.set(false)">
            <a routerLink="/" fragment="hero" class="block text-sm text-muted-foreground hover:text-foreground">Redesign My Site</a>
            <a routerLink="/" fragment="how-it-works" class="block text-sm text-muted-foreground hover:text-foreground">How It Works</a>
            <a routerLink="/pricing" routerLinkActive="!text-primary" class="block text-sm text-muted-foreground hover:text-foreground">Pricing</a>
            @if (lastProjectId() && !onProject()) {
              <a [routerLink]="['/projects', lastProjectId()]" class="block text-sm text-primary hover:text-primary/80">View My Redesign</a>
            }
            @if (auth.isAuthenticated()) {
              <a routerLink="/history" routerLinkActive="!text-primary" class="block text-sm text-muted-foreground hover:text-foreground">History</a>
              <a routerLink="/settings/billing" routerLinkActive="!text-primary" class="block text-sm text-muted-foreground hover:text-foreground">Billing</a>
              @if (wallet.balance() !== null) {
                <a routerLink="/checkout" class="block text-sm text-muted-foreground hover:text-foreground">
                  {{ wallet.balance() }} credit{{ wallet.balance() === 1 ? '' : 's' }} · Buy more
                </a>
              }
              @if (auth.currentUser()?.is_admin) {
                <a routerLink="/admin" class="block text-sm text-muted-foreground hover:text-foreground">Admin</a>
              }
              <a uiButton size="sm" routerLink="/history" class="w-full bg-primary text-white">Dashboard</a>
            } @else {
              <div class="flex gap-2">
                <a uiButton variant="outline" size="sm" routerLink="/login" class="flex-1">Sign In</a>
                <a uiButton size="sm" routerLink="/login" class="flex-1 bg-primary text-white">Get Started</a>
              </div>
            }
          </div>
        </div>
      </div>
    </nav>
  `,
})
export class NavbarComponent {
  protected readonly icons = { ArrowRight, Coins, Menu, Shield, X };
  protected readonly auth = inject(AuthService);
  protected readonly wallet = inject(WalletService);
  protected readonly open = signal(false);

  private readonly router = inject(Router);
  private readonly url = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      map((e) => (e as NavigationEnd).urlAfterRedirects),
    ),
    { initialValue: this.router.url },
  );
  protected readonly onProject = computed(() => this.url().startsWith('/projects/'));
  protected readonly lastProjectId = computed(() => {
    this.url();
    return this.auth.isAuthenticated() ? readLastProjectId() : null;
  });
}
