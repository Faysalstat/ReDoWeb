import { Component, input } from '@angular/core';

/** Shared shell for the static legal pages. */
@Component({
  selector: 'app-legal-page',
  standalone: true,
  template: `
    <section class="py-20 px-4">
      <article class="max-w-3xl mx-auto rounded-2xl border border-border/50 bg-card/50 backdrop-blur-sm p-6 sm:p-10">
        <span class="text-sm font-semibold text-primary uppercase tracking-wider block mb-4">Legal</span>
        <h1 class="text-3xl sm:text-4xl font-black mb-2">{{ title() }}</h1>
        <p class="text-sm text-muted-foreground mb-10">Last updated {{ updated() }}</p>
        <div
          class="space-y-6 text-muted-foreground [&_h2]:text-foreground [&_h2]:text-xl [&_h2]:font-bold [&_h2]:mt-10 [&_h2]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-2 [&_strong]:text-foreground"
        >
          <ng-content />
        </div>
      </article>
    </section>
  `,
})
export class LegalPageComponent {
  readonly title = input.required<string>();
  readonly updated = input.required<string>();
}
