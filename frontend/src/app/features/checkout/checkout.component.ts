import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, NgZone, OnDestroy, OnInit, computed, inject, signal, viewChild } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { firstValueFrom, forkJoin } from 'rxjs';

import { PayPalButtonsInstance, PayPalSdkLoader } from '../../core/paypal-sdk.loader';
import { BillingConfigResponse, CreditPack } from '../../core/redowebs-api.models';
import { RedoWebsApiService } from '../../core/redowebs-api.service';
import { WalletService } from '../../core/wallet.service';
import { formatUsd } from '../../shared/ui/credit-pack-grid/credit-pack-grid.component';

type CheckoutState =
  | 'loading'
  | 'ready'
  | 'processing'
  | 'success'
  | 'pending'
  | 'error'
  | 'cancelled'
  | 'unavailable'
  | 'no-packs';

/** Only same-app paths are allowed as a post-payment destination -- an
 * absolute or protocol-relative URL here would make /checkout an open
 * redirect. Exported for unit testing. */
export function safeReturnUrl(raw: string | null): string {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//') || raw.startsWith('/\\')) {
    return '/history';
  }
  return raw;
}

/** Credit-pack checkout via PayPal Smart Buttons (PayPal account or card).
 * The backend creates the order from the selected pack's server-side price
 * and captures it on approval; credits land exactly once even if PayPal's
 * webhook also fires (see docs/paypal-payments-plan.md).
 *
 * Query params: `pack` preselects a pack; `credits` (a shortfall from the
 * download/cost-gate prompts) preselects the smallest pack that covers it;
 * `returnUrl` is where "Continue" goes after paying. */
@Component({
  selector: 'app-checkout',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './checkout.component.html',
  styleUrl: './checkout.component.css',
})
export class CheckoutComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  readonly requestedCredits = Number(this.route.snapshot.queryParamMap.get('credits')) || null;
  readonly returnUrl = safeReturnUrl(this.route.snapshot.queryParamMap.get('returnUrl'));
  private readonly requestedPackId = this.route.snapshot.queryParamMap.get('pack');

  readonly packs = signal<CreditPack[]>([]);
  readonly selectedPackId = signal<string | null>(null);
  readonly state = signal<CheckoutState>('loading');
  readonly message = signal('');
  readonly creditsAdded = signal(0);
  /** Local test mode (REDOWEBS_PAYMENTS_MODE=mock): a plain button stands in
   * for PayPal and every payment succeeds -- same backend endpoints. */
  readonly mockMode = signal(false);

  readonly selectedPack = computed(() => this.packs().find((p) => p.id === this.selectedPackId()) ?? null);
  readonly balanceAfter = computed(() => {
    const balance = this.wallet.balance();
    const pack = this.selectedPack();
    return balance !== null && pack ? balance + pack.credits : null;
  });

  private readonly buttonsHost = viewChild<ElementRef<HTMLElement>>('paypalButtons');
  private buttons?: PayPalButtonsInstance;
  private config?: BillingConfigResponse;

  constructor(
    private readonly api: RedoWebsApiService,
    private readonly sdk: PayPalSdkLoader,
    private readonly router: Router,
    private readonly zone: NgZone,
    readonly wallet: WalletService
  ) {}

  ngOnInit(): void {
    forkJoin({ config: this.api.getBillingConfig(), packs: this.api.getCreditPacks() }).subscribe({
      next: ({ config, packs }) => {
        this.config = config;
        this.packs.set(packs.items);
        if (!config.enabled) {
          this.state.set('unavailable');
          return;
        }
        if (packs.items.length === 0) {
          this.state.set('no-packs');
          return;
        }
        this.selectedPackId.set(this.initialPackId(packs.items));
        this.state.set('ready');
        if (config.mode === 'mock') {
          this.mockMode.set(true);
          return;
        }
        // Let the @if render the button host before PayPal draws into it.
        setTimeout(() => this.renderButtons());
      },
      error: () => this.fail("Checkout couldn't be loaded. Please refresh and try again."),
    });
  }

  ngOnDestroy(): void {
    this.buttons?.close().catch(() => {});
  }

  price(cents: number): string {
    return formatUsd(cents);
  }

  perCredit(pack: CreditPack): string {
    return `$${(pack.price_usd_cents / pack.credits / 100).toFixed(2)}`;
  }

  select(packId: string): void {
    if (this.state() === 'ready' || this.state() === 'cancelled' || this.state() === 'error') {
      this.selectedPackId.set(packId);
    }
  }

  /** Test mode: the same create -> capture calls PayPal's buttons make,
   * minus the PayPal popup. */
  async payWithMock(): Promise<void> {
    try {
      const orderId = await this.createOrder();
      await this.onApprove(orderId, { restart: async () => {} });
    } catch {
      // createOrder() already put the error on screen.
    }
  }

  continue(): void {
    this.router.navigateByUrl(this.returnUrl);
  }

  tryAgain(): void {
    this.message.set('');
    this.state.set('ready');
  }

  /** Smallest pack that covers the shortfall, else the largest pack;
   * an explicit ?pack= wins if it's still on sale. */
  private initialPackId(packs: CreditPack[]): string {
    if (this.requestedPackId && packs.some((p) => p.id === this.requestedPackId)) {
      return this.requestedPackId;
    }
    if (this.requestedCredits) {
      const covering = packs
        .filter((p) => p.credits >= this.requestedCredits!)
        .sort((a, b) => a.credits - b.credits);
      if (covering.length > 0) {
        return covering[0].id;
      }
      return [...packs].sort((a, b) => b.credits - a.credits)[0].id;
    }
    return packs[0].id;
  }

  private async renderButtons(): Promise<void> {
    const host = this.buttonsHost()?.nativeElement;
    if (!host || !this.config) {
      return;
    }
    try {
      const paypal = await this.sdk.load(this.config);
      this.buttons = paypal.Buttons({
        style: { layout: 'vertical', shape: 'rect', label: 'pay', height: 48 },
        createOrder: () => this.zone.run(() => this.createOrder()),
        onApprove: (data, actions) => this.zone.run(() => this.onApprove(data.orderID, actions)),
        onCancel: () =>
          this.zone.run(() => {
            this.state.set('cancelled');
            this.message.set('Payment cancelled — nothing was charged.');
          }),
        onError: () =>
          this.zone.run(() => {
            if (this.state() !== 'error') {
              this.fail('PayPal ran into a problem. Nothing was charged — please try again.');
            }
          }),
      });
      await this.buttons.render(host);
    } catch {
      this.zone.run(() => this.fail("PayPal couldn't be loaded. Check your connection or ad blocker and refresh."));
    }
  }

  private async createOrder(): Promise<string> {
    const packId = this.selectedPackId();
    if (!packId) {
      throw new Error('No pack selected');
    }
    this.message.set('');
    this.state.set('processing');
    try {
      const order = await firstValueFrom(this.api.createPayPalOrder(packId));
      return order.order_id;
    } catch (err) {
      this.fail(this.errorText(err, "We couldn't start the payment. Please try again."));
      throw err;
    }
  }

  private async onApprove(orderId: string, actions: { restart(): Promise<void> }): Promise<void> {
    this.state.set('processing');
    try {
      const result = await firstValueFrom(this.api.capturePayPalOrder(orderId));
      if (result.status === 'completed') {
        this.wallet.set(result.balance);
        this.creditsAdded.set(result.credits_granted);
        this.state.set('success');
        return;
      }
      if (result.status === 'pending') {
        this.state.set('pending');
        this.message.set(result.reason ?? 'PayPal is still processing this payment.');
        return;
      }
      if (result.reason === 'INSTRUMENT_DECLINED') {
        // PayPal's recommended recovery: reopen the popup so the buyer can
        // pick another card/funding source for the same order.
        this.state.set('ready');
        await actions.restart();
        return;
      }
      this.fail(`The payment didn't go through (${result.reason ?? 'unknown reason'}). You have not been charged credits.`);
    } catch (err) {
      // The capture may still have succeeded at PayPal -- the webhook will
      // credit it. Say so rather than implying the money was lost.
      this.state.set('pending');
      this.message.set(
        this.errorText(err, "We couldn't confirm the payment yet. If you were charged, your credits will appear shortly.")
      );
    }
  }

  private fail(text: string): void {
    this.message.set(text);
    this.state.set('error');
  }

  private errorText(err: unknown, fallback: string): string {
    const detail = err instanceof HttpErrorResponse ? err.error?.detail : null;
    return typeof detail === 'string' ? detail : fallback;
  }
}
