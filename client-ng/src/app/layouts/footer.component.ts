import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { BrandMarkComponent } from '../shared/components/brand-mark.component';
import { TRUSTED_LOGOS } from '../pages/home/home-content';

/** Blueprint §6.4 footer: "trusted by" strip (placeholder content, see
 * home-content.ts), then link columns that only point at real pages. */
@Component({
  selector: 'app-footer',
  standalone: true,
  imports: [RouterLink, BrandMarkComponent],
  host: { class: 'block' },
  template: `
    <footer class="border-t border-border/50 bg-background">
      <div class="py-12">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p class="text-center text-xs font-bold text-muted-foreground mb-8 tracking-widest">TRUSTED BY LEADING COMPANIES</p>
          <div class="flex flex-wrap items-center justify-center gap-8 sm:gap-12 md:gap-16 lg:gap-20">
            @for (logo of trustedLogos; track logo.alt) {
              <div class="h-14 flex items-center">
                <img [src]="logo.src" [alt]="logo.alt" class="h-full object-contain opacity-75 hover:opacity-100 transition-opacity" />
              </div>
            }
          </div>
        </div>
      </div>

      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div class="col-span-2 md:col-span-1">
            <a routerLink="/" class="inline-flex mb-4"><app-brand-mark /></a>
            <p class="text-sm text-muted-foreground leading-relaxed">
              AI-generated redesigns of your existing site — your facts kept intact, nothing published without your word.
            </p>
          </div>
          @for (col of columns; track col.title) {
            <div>
              <h4 class="font-semibold text-sm mb-4">{{ col.title }}</h4>
              <div class="space-y-2">
                @for (l of col.links; track l.label) {
                  <a
                    [routerLink]="l.path"
                    [fragment]="l.fragment"
                    class="block text-sm text-muted-foreground hover:text-foreground transition-colors"
                    >{{ l.label }}</a
                  >
                }
              </div>
            </div>
          }
        </div>
      </div>

      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div class="border-t border-border/50 pt-6 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p class="text-xs text-muted-foreground">© 2026 ReDoWebs. All rights reserved.</p>
          <p class="text-xs text-muted-foreground">We only redesign sites you own or are authorized to submit.</p>
        </div>
      </div>
    </footer>
  `,
})
export class FooterComponent {
  protected readonly trustedLogos = TRUSTED_LOGOS;
  protected readonly columns: { title: string; links: { label: string; path: string; fragment?: string }[] }[] = [
    {
      title: 'Product',
      links: [
        { label: 'How It Works', path: '/', fragment: 'how-it-works' },
        { label: 'Features', path: '/', fragment: 'features' },
        { label: 'Pricing', path: '/pricing' },
      ],
    },
    {
      title: 'Account',
      links: [
        { label: 'History', path: '/history' },
        { label: 'Billing', path: '/settings/billing' },
        { label: 'Buy credits', path: '/checkout' },
      ],
    },
    {
      title: 'Legal',
      links: [
        { label: 'Privacy', path: '/privacy' },
        { label: 'Terms', path: '/terms' },
      ],
    },
  ];
}
