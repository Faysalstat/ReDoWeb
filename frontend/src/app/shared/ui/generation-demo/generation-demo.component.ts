import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';

import { StepItemComponent, StepStatus } from '../step-item/step-item.component';

type DemoPhase = 'crawling' | 'extracting' | 'generating';

const PHASES: DemoPhase[] = ['crawling', 'extracting', 'generating'];
const PHASE_MS = 2600;

const SUBSTATUS: Record<DemoPhase, string> = {
  crawling: 'Fetching pages and assets…',
  extracting: 'Detecting brand colors and fonts…',
  generating: 'Writing HTML, CSS, and copy…',
};

/**
 * Purely decorative auto-cycling mockup of the crawl -> extract -> generate
 * pipeline for the marketing page. Not wired to any real project/status data.
 */
@Component({
  selector: 'app-generation-demo',
  standalone: true,
  imports: [StepItemComponent],
  host: { class: 'block' },
  template: `
    <div class="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:items-center">
      <div>
        <p class="font-mono text-xs uppercase tracking-widest text-accent-bright">Live look</p>
        <h3 class="mt-2 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
          Watch the pipeline work
        </h3>
        <p class="mt-3 text-sm leading-relaxed text-ink-muted">
          A simulated look at what happens after you hit "Generate My Redesign" — your real
          project shows this same sequence with live status updates.
        </p>
        <ol class="mt-8 space-y-5">
          <li
            appStepItem
            [index]="1"
            label="Crawling your site"
            description="Reading pages, content, and brand assets"
            [subStatus]="subStatusFor('crawling')"
            [status]="statusFor('crawling')"
          ></li>
          <li
            appStepItem
            [index]="2"
            label="Extracting your brand blueprint"
            description="Identifying your logo, colors, fonts, and tone"
            [subStatus]="subStatusFor('extracting')"
            [status]="statusFor('extracting')"
          ></li>
          <li
            appStepItem
            [index]="3"
            label="Generating your new design"
            description="Writing modern HTML, CSS, and copy"
            [subStatus]="subStatusFor('generating')"
            [status]="statusFor('generating')"
          ></li>
        </ol>
      </div>

      <div
        class="relative aspect-[4/3] overflow-hidden rounded-2xl border border-white/6 bg-canvas-elevated shadow-card"
      >
        <div class="flex items-center gap-2 border-b border-white/10 bg-canvas-elevated/80 px-4 py-3">
          <span class="h-3 w-3 rounded-full bg-red-400"></span>
          <span class="h-3 w-3 rounded-full bg-amber-400"></span>
          <span class="h-3 w-3 rounded-full bg-emerald-400"></span>
        </div>

        <div class="relative h-[calc(100%-2.75rem)] w-full">
          <!-- Before: dated, boxy wireframe -->
          <div
            class="motion-reduce:transition-none absolute inset-0 p-6 transition-opacity duration-700"
            [class.opacity-0]="showAfter()"
            [class.opacity-100]="!showAfter()"
          >
            <div class="h-4 w-24 rounded bg-white/10"></div>
            <div class="mt-4 h-16 w-full rounded bg-white/5"></div>
            <div class="mt-4 grid grid-cols-3 gap-3">
              <div class="h-14 rounded bg-white/5"></div>
              <div class="h-14 rounded bg-white/5"></div>
              <div class="h-14 rounded bg-white/5"></div>
            </div>
          </div>

          <!-- After: modern, glowing, rounded -->
          <div
            class="motion-reduce:transition-none absolute inset-0 p-6 transition-opacity duration-700"
            [class.opacity-100]="showAfter()"
            [class.opacity-0]="!showAfter()"
          >
            <div class="h-4 w-28 rounded-full bg-gradient-to-r from-accent to-accent-bright"></div>
            <div class="mt-4 h-16 w-full rounded-xl bg-gradient-to-br from-accent/30 to-transparent shadow-cta-glow"></div>
            <div class="mt-4 grid grid-cols-3 gap-3">
              <div class="h-14 rounded-xl border border-accent/30 bg-accent/10"></div>
              <div class="h-14 rounded-xl border border-accent/30 bg-accent/10"></div>
              <div class="h-14 rounded-xl border border-accent/30 bg-accent/10"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
})
export class GenerationDemoComponent implements OnInit, OnDestroy {
  private readonly phaseIndex = signal(0);
  private timer?: ReturnType<typeof setInterval>;

  protected readonly showAfter = computed(() => PHASES[this.phaseIndex()] === 'generating');

  ngOnInit(): void {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      this.phaseIndex.set(PHASES.length - 1);
      return;
    }
    this.timer = setInterval(() => {
      this.phaseIndex.set((this.phaseIndex() + 1) % PHASES.length);
    }, PHASE_MS);
  }

  ngOnDestroy(): void {
    if (this.timer) {
      clearInterval(this.timer);
    }
  }

  protected statusFor(step: DemoPhase): StepStatus {
    const order = PHASES.indexOf(step);
    const current = this.phaseIndex();
    if (order < current) {
      return 'done';
    }
    return order === current ? 'active' : 'pending';
  }

  protected subStatusFor(step: DemoPhase): string {
    return this.statusFor(step) === 'active' ? SUBSTATUS[step] : '';
  }
}
