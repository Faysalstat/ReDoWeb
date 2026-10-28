import { Injectable } from '@angular/core';

import { BillingConfigResponse } from './redowebs-api.models';

/** Minimal typing for the bits of the PayPal JS SDK the checkout uses. */
export interface PayPalButtonsInstance {
  render(container: HTMLElement): Promise<void>;
  close(): Promise<void>;
  isEligible(): boolean;
}

export interface PayPalNamespace {
  Buttons(options: {
    fundingSource?: string;
    style?: Record<string, string | number | boolean>;
    createOrder: () => Promise<string>;
    onApprove: (data: { orderID: string }, actions: { restart(): Promise<void> }) => Promise<void>;
    onCancel?: () => void;
    onError?: (err: unknown) => void;
  }): PayPalButtonsInstance;
  FUNDING: { PAYPAL: string; CARD: string };
}

declare global {
  interface Window {
    paypal?: PayPalNamespace;
  }
}

/** Injects the PayPal JS SDK <script> once per page load, configured from
 * GET /billing/config (so no PayPal settings are baked into the build).
 * `enable-funding=card` makes the "Debit or Credit Card" button available
 * for buyers without a PayPal account -- it still only shows if the
 * business account allows guest checkout ("PayPal account optional"). */
@Injectable({ providedIn: 'root' })
export class PayPalSdkLoader {
  private loading?: Promise<PayPalNamespace>;

  load(config: BillingConfigResponse): Promise<PayPalNamespace> {
    if (window.paypal) {
      return Promise.resolve(window.paypal);
    }
    if (this.loading) {
      return this.loading;
    }
    const params = new URLSearchParams({
      'client-id': config.paypal_client_id,
      currency: config.currency,
      intent: 'capture',
      components: 'buttons',
      'enable-funding': 'card',
      // Only PayPal + card, as decided for v1 -- no Pay Later / Venmo.
      'disable-funding': 'paylater,venmo',
    });
    this.loading = new Promise<PayPalNamespace>((resolve, reject) => {
      const script = document.createElement('script');
      script.src = `https://www.paypal.com/sdk/js?${params.toString()}`;
      script.async = true;
      script.onload = () => (window.paypal ? resolve(window.paypal) : reject(new Error('PayPal SDK missing')));
      script.onerror = () => {
        this.loading = undefined;
        script.remove();
        reject(new Error('Could not load PayPal'));
      };
      document.head.appendChild(script);
    });
    return this.loading;
  }
}
