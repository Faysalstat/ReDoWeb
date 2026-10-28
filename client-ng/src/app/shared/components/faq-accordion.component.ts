import { Component, input, signal } from '@angular/core';
import { ChevronDown, LucideAngularModule } from 'lucide-angular';

import { RevealDirective } from '../motion/reveal.directive';

export interface Faq {
  q: string;
  a: string;
}

/** Blueprint §7.7: one item open at a time, the first open by default. */
@Component({
  selector: 'app-faq-accordion',
  standalone: true,
  imports: [LucideAngularModule, RevealDirective],
  host: { class: 'block' },
  template: `
    <div class="space-y-3">
      @for (faq of faqs(); track faq.q; let i = $index) {
        <div reveal [revealDelay]="i * 50" [revealY]="10">
          <button
            type="button"
            (click)="open.set(open() === i ? -1 : i)"
            [attr.aria-expanded]="open() === i"
            class="w-full flex items-center justify-between gap-4 p-5 rounded-xl border border-border/40 bg-card/30 hover:bg-card/60 transition-colors text-left"
          >
            <span class="font-semibold">{{ faq.q }}</span>
            <lucide-icon
              [img]="ChevronDown"
              class="w-5 h-5 text-primary transition-transform"
              [class]="open() === i ? 'rotate-180' : ''"
            />
          </button>
          <div
            class="grid transition-all duration-200"
            [class]="open() === i ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'"
          >
            <div class="overflow-hidden">
              <div class="p-5 border border-t-0 border-border/40 rounded-b-xl bg-card/20">
                <p class="text-muted-foreground">{{ faq.a }}</p>
              </div>
            </div>
          </div>
        </div>
      }
    </div>
  `,
})
export class FaqAccordionComponent {
  readonly faqs = input.required<Faq[]>();
  protected readonly open = signal(0);
  protected readonly ChevronDown = ChevronDown;
}
