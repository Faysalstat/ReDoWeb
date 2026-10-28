import { Component } from '@angular/core';

import { LegalPageComponent } from './legal-page.component';

// Plain-language summary of what the app stores. Not reviewed by a lawyer;
// replace with a reviewed policy before launch.
@Component({
  selector: 'app-privacy-page',
  standalone: true,
  imports: [LegalPageComponent],
  template: `
    <app-legal-page title="Privacy Policy" updated="October 2026">
      <p>This page explains what ReDoWebs stores about you and why.</p>

      <h2>What we store</h2>
      <ul>
        <li><strong>Your account:</strong> the name and email address from your Google sign-in.</li>
        <li><strong>Your projects:</strong> the URLs you submit, the public pages we read from them, and the designs we generate.</li>
        <li><strong>Your credits:</strong> your balance and a record of every purchase and credit spend.</li>
      </ul>

      <h2>Payments</h2>
      <p>
        Payments are processed by PayPal. Card details are entered with PayPal, and ReDoWebs never sees or stores them.
      </p>

      <h2>How long we keep it</h2>
      <ul>
        <li>Previews of designs you didn't buy, and the copy of your site we read, are deleted after a limited time.</li>
        <li>Designs you bought are kept so you can download them again.</li>
      </ul>

      <h2>In your browser</h2>
      <p>
        We keep your sign-in in your browser's session storage, and the last project you submitted in local storage so the
        "View My Redesign" link can find it. Nothing is used for advertising.
      </p>
    </app-legal-page>
  `,
})
export default class PrivacyPage {}
