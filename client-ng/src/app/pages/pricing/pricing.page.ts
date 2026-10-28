import { Component } from '@angular/core';

import { CreditPackGridComponent } from '../../shared/components/credit-pack-grid.component';
import { Faq, FaqAccordionComponent } from '../../shared/components/faq-accordion.component';
import { RevealDirective } from '../../shared/motion/reveal.directive';

/** Public pricing page: real, admin-configured credit packs and tier
 * download costs (see CreditPackGridComponent), plus pricing FAQs. */
@Component({
  selector: 'app-pricing-page',
  standalone: true,
  imports: [CreditPackGridComponent, FaqAccordionComponent, RevealDirective],
  template: `
    <section class="py-20 sm:py-24 px-4 border-b border-border/20">
      <div class="max-w-5xl mx-auto text-center">
        <div reveal class="mb-16">
          <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-primary/30 bg-primary/5 mb-6">
            <span class="text-xs font-medium text-primary">One-time credit packs · no subscription</span>
          </div>
          <h1 class="text-4xl sm:text-5xl font-black mb-4">Preview Costs Nothing. Downloading Costs Credits.</h1>
          <p class="text-muted-foreground text-lg max-w-2xl mx-auto">
            Every design includes a free live preview. Buy a credit pack once and spend credits only on the redesigns you
            want to keep.
          </p>
        </div>
        <app-credit-pack-grid />
      </div>
    </section>

    <section class="py-20 px-4">
      <div class="max-w-2xl mx-auto">
        <h2 class="text-3xl sm:text-4xl font-black text-center mb-4">Pricing Questions</h2>
        <p class="text-center text-muted-foreground mb-12">How credits work.</p>
        <app-faq-accordion [faqs]="faqs" />
      </div>
    </section>
  `,
})
export default class PricingPage {
  protected readonly faqs: Faq[] = [
    { q: 'What is a credit?', a: 'Credits are what you spend in ReDoWebs. You buy them in one-time packs; there is no subscription.' },
    { q: 'What do credits pay for?', a: 'Each generation costs 1 credit, and buying a design costs that tier\'s price in credits. Previews are free, and re-downloading a design you already bought is free.' },
    { q: 'What does buying a design include?', a: 'The ZIP download, and once per purchase: generating every page of a multi-page site, and on Pro and Premium the SEO agent. If one of those fails you can retry it.' },
    { q: 'How do I pay?', a: 'With PayPal or any debit or credit card through PayPal. You don\'t need a PayPal account, and ReDoWebs never sees your card details.' },
  ];
}
