import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';

import { IconCheck, IconSparkles } from './icons';

type DemoPhase = 'crawling' | 'extracting' | 'generating';
const PHASES: DemoPhase[] = ['crawling', 'extracting', 'generating'];
const PHASE_MS = 2600;

/** Purely decorative auto-cycling mockup of the crawl -> extract -> generate
 * pipeline for the homepage (playful take on the classic GenerationDemo).
 * Not wired to any real project/status data. */
@Component({
  selector: 'pg-pipeline-demo',
  standalone: true,
  imports: [IconCheck, IconSparkles],
  template: `
    <div class="pd">
      <div class="pd__copy">
        <span class="pg-kicker">Live look</span>
        <h2 class="pd__title">Watch the pipeline <span class="pg-squiggle" style="--pg-squiggle-color: var(--pg-mint)">work</span></h2>
        <p class="pg-muted">
          A simulated look at what happens after you submit your URL. Your real project shows the same sequence with live
          status updates.
        </p>
        <ol class="pd__steps">
          @for (step of steps; track step.key; let i = $index) {
            <li class="pd__step" [class]="'is-' + statusFor(step.key)" [style.--c]="colors[i]">
              <span class="pd__node" aria-hidden="true">
                @if (statusFor(step.key) === 'done') { <app-icon-check [size]="16" /> } @else { {{ i + 1 }} }
              </span>
              <span class="pd__text">
                <b>{{ step.label }}</b>
                <span class="pg-muted">{{ statusFor(step.key) === 'active' ? step.sub : step.description }}</span>
              </span>
            </li>
          }
        </ol>
      </div>

      <div class="pg-card pd__panel" aria-hidden="true">
        <div class="pd__head">
          <span class="pd__live"></span>
          <span class="pg-label">Live · rebuilding yourbusiness.com</span>
        </div>
        <div class="pd__mocks">
          <div class="pd__mock pd__mock--old">
            <span class="pg-chip">Before</span>
            <i style="width: 70%"></i><i style="width: 45%"></i><i class="pd__img"></i><i style="width: 85%"></i>
          </div>
          <div class="pd__mock pd__mock--new" [class.is-built]="phase() === 'generating'">
            <span class="pg-chip pg-chip--mint"><app-icon-sparkles [size]="12" /> After</span>
            <i class="pd__h" style="width: 80%"></i><i class="pd__h" style="width: 55%"></i>
            <span class="pd__btn"></span>
            <span class="pd__cards"><b></b><b></b><b></b></span>
          </div>
        </div>
        <div class="pg-meter pg-meter--sm"><span [style.width.%]="progressPercent()"></span></div>
      </div>
    </div>
  `,
  styles: [
    `
      .pd { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 56px; align-items: center; }
      .pd__copy { display: grid; gap: 16px; justify-items: start; }
      .pd__title { font-size: clamp(1.9rem, 3.6vw, var(--pg-text-3xl)); }
      .pd__steps { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 12px; width: 100%; }
      .pd__step { display: flex; align-items: center; gap: 14px; padding: 12px 14px; border: 2px solid transparent; border-radius: var(--pg-radius-md); transition: background-color 300ms, border-color 300ms; }
      .pd__node {
        display: grid; place-items: center; flex: none; width: 40px; height: 40px; border-radius: 50%;
        border: 2px solid var(--pg-fg); background: var(--pg-muted); color: var(--pg-muted-fg); font: 800 1rem/1 var(--pg-font-heading);
        transition: transform 300ms var(--pg-bounce), background-color 300ms;
      }
      .pd__text { display: grid; font-size: var(--pg-text-sm); line-height: 1.35; }
      .pd__text b { font-family: var(--pg-font-heading); font-size: var(--pg-text-md); }
      .pd__step.is-active { background: var(--pg-card); border-color: var(--pg-fg); box-shadow: 4px 4px 0 var(--c); }
      .pd__step.is-active .pd__node { background: var(--c); color: var(--pg-fg); transform: scale(1.1); }
      .pd__step.is-done .pd__node { background: var(--pg-mint); color: var(--pg-fg); }
      .pd__panel { display: grid; gap: 18px; padding: 22px; box-shadow: 8px 8px 0 var(--pg-fg); }
      .pd__head { display: flex; align-items: center; gap: 10px; }
      .pd__live { width: 12px; height: 12px; border-radius: 50%; background: var(--pg-mint); border: 2px solid var(--pg-fg); animation: pd-blink 1.4s infinite; }
      @keyframes pd-blink { 50% { opacity: 0.25; } }
      .pd__mocks { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
      .pd__mock { display: grid; align-content: start; gap: 8px; min-height: 170px; padding: 14px; border: 2px solid var(--pg-fg); border-radius: var(--pg-radius-sm); }
      .pd__mock .pg-chip { justify-self: start; margin-bottom: 4px; }
      .pd__mock i { display: block; height: 7px; border-radius: 4px; background: #cbd5e1; }
      .pd__mock--old { background: var(--pg-muted); filter: saturate(0.3); }
      .pd__mock--old .pd__img { height: 48px; background: #e2e8f0; }
      .pd__mock--new { background: var(--pg-card); }
      .pd__mock--new .pd__h { height: 10px; background: var(--pg-fg); }
      .pd__btn { width: 54px; height: 16px; border-radius: 99px; background: var(--pg-accent); border: 2px solid var(--pg-fg); }
      .pd__cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 4px; }
      .pd__cards b { height: 28px; border-radius: 6px; border: 2px solid var(--pg-fg); background: var(--pg-muted); transition: background-color 400ms; }
      .is-built .pd__cards b:nth-child(1) { background: var(--pg-accent); }
      .is-built .pd__cards b:nth-child(2) { background: var(--pg-pink); }
      .is-built .pd__cards b:nth-child(3) { background: var(--pg-amber); }
      @media (max-width: 960px) { .pd { grid-template-columns: 1fr; gap: 36px; } }
      @media (max-width: 640px) { .pd__panel { box-shadow: 4px 4px 0 var(--pg-fg); } }
    `,
  ],
})
export class PgPipelineDemoComponent implements OnInit, OnDestroy {
  private readonly phaseIndex = signal(0);
  private timer?: ReturnType<typeof setInterval>;

  readonly colors = ['var(--pg-accent)', 'var(--pg-pink)', 'var(--pg-amber)'];
  readonly steps: { key: DemoPhase; label: string; description: string; sub: string }[] = [
    { key: 'crawling', label: 'Crawling your site', description: 'Reading pages, content and brand assets', sub: 'Fetching pages and assets…' },
    { key: 'extracting', label: 'Extracting your brand blueprint', description: 'Finding your logo, colors, fonts and tone', sub: 'Detecting brand colors and fonts…' },
    { key: 'generating', label: 'Generating your new design', description: 'Writing modern HTML, CSS and copy', sub: 'Writing HTML, CSS and copy…' },
  ];

  readonly phase = computed(() => PHASES[this.phaseIndex()]);
  readonly progressPercent = computed(() => ((this.phaseIndex() + 1) / PHASES.length) * 100);

  ngOnInit(): void {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      this.phaseIndex.set(PHASES.length - 1);
      return;
    }
    this.timer = setInterval(() => this.phaseIndex.set((this.phaseIndex() + 1) % PHASES.length), PHASE_MS);
  }

  ngOnDestroy(): void {
    if (this.timer) {
      clearInterval(this.timer);
    }
  }

  statusFor(step: DemoPhase): 'done' | 'active' | 'pending' {
    const order = PHASES.indexOf(step);
    const current = this.phaseIndex();
    return order < current ? 'done' : order === current ? 'active' : 'pending';
  }
}
