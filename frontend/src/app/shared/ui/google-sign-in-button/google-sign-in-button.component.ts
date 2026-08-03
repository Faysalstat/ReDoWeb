import { AfterViewInit, Component, ElementRef, output, viewChild } from '@angular/core';

import { GOOGLE_CLIENT_ID } from '../../../core/api-config';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }): void;
          renderButton(parent: HTMLElement, options: Record<string, unknown>): void;
        };
      };
    };
  }
}

const GSI_POLL_INTERVAL_MS = 250;
const GSI_POLL_MAX_ATTEMPTS = 40; // ~10s -- the GIS <script> loads async/defer

/** Thin wrapper around Google Identity Services' hosted "Sign in with
 * Google" button. Emits the raw ID token (JWT) on `credential` for the
 * backend to verify -- this component never itself decides who's signed in. */
@Component({
  selector: 'app-google-sign-in-button',
  standalone: true,
  template: `<div #buttonContainer></div>`,
})
export class GoogleSignInButtonComponent implements AfterViewInit {
  readonly credential = output<string>();

  private readonly buttonContainer = viewChild.required<ElementRef<HTMLDivElement>>('buttonContainer');

  ngAfterViewInit(): void {
    this.renderWhenReady();
  }

  private renderWhenReady(attempt = 0): void {
    if (!window.google?.accounts?.id) {
      if (attempt >= GSI_POLL_MAX_ATTEMPTS) {
        return;
      }
      setTimeout(() => this.renderWhenReady(attempt + 1), GSI_POLL_INTERVAL_MS);
      return;
    }

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: (response) => this.credential.emit(response.credential),
    });
    window.google.accounts.id.renderButton(this.buttonContainer().nativeElement, {
      theme: 'outline',
      size: 'large',
      shape: 'pill',
    });
  }
}
