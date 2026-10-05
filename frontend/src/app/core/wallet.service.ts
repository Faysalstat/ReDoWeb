import { Injectable, effect, signal } from '@angular/core';

import { AuthService } from './auth.service';
import { RedoWebsApiService } from './redowebs-api.service';

/** Single shared credit balance for the whole app. Loads on login, clears
 * on logout, and anything that changes the balance (a purchase, a download
 * charge, a generation) calls refresh() -- or set() when the server already
 * returned the new balance -- so the header updates immediately instead of
 * only on the next login. */
@Injectable({ providedIn: 'root' })
export class WalletService {
  readonly balance = signal<number | null>(null);

  constructor(
    private readonly auth: AuthService,
    private readonly api: RedoWebsApiService
  ) {
    effect(() => {
      if (this.auth.isAuthenticated()) {
        this.refresh();
      } else {
        this.balance.set(null);
      }
    });
  }

  refresh(): void {
    if (!this.auth.isAuthenticated()) {
      return;
    }
    this.api.getWallet().subscribe({
      next: (wallet) => this.balance.set(wallet.balance),
      error: () => {},
    });
  }

  set(balance: number): void {
    this.balance.set(balance);
  }
}
