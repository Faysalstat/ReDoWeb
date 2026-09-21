import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';

import { SiteMockComponent } from '../site-mock/site-mock.component';
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
  imports: [StepItemComponent, SiteMockComponent],
  host: { style: 'display: block' },
  template: `
    <div class="demo">
      <div>
        <span class="kicker">Live look</span>
        <h3 style="margin-top: var(--space-2)">Watch the pipeline work</h3>
        <p class="sub" style="margin-top: var(--space-3)">
          A simulated look at what happens after you submit your URL — your real project shows this
          same sequence with live status updates.
        </p>
        <ol class="stack" style="margin-top: var(--space-6); list-style: none; padding: 0">
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

      <aside class="panel">
        <div class="panel__head">
          <span class="row" style="gap: var(--space-2)">
            <span style="width: 10px; height: 10px; border-radius: 50%; background: var(--color-success)"></span>
            <span class="label">Live · rebuilding yourbusiness.com</span>
          </span>
        </div>
        <div class="panel__body stack">
          <div class="demo__mocks">
            <div>
              <span class="label">Before</span>
              <app-site-mock variant="old" [height]="150" />
            </div>
            <div>
              <span class="label" style="color: var(--color-success)">After</span>
              <app-site-mock variant="new" [height]="150" />
            </div>
          </div>
          <div class="meter" style="height: 2px">
            <div class="meter__fill" [style.width.%]="progressPercent()"></div>
          </div>
        </div>
      </aside>
    </div>
  `,
  styles: [
    `
      .demo {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: var(--space-8);
      }
      @media (min-width: 980px) {
        .demo {
          grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
          align-items: center;
        }
      }
      .demo__mocks {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--space-3);
      }
    `,
  ],
})
export class GenerationDemoComponent implements OnInit, OnDestroy {
  private readonly phaseIndex = signal(0);
  private timer?: ReturnType<typeof setInterval>;

  protected readonly progressPercent = computed(() => ((this.phaseIndex() + 1) / PHASES.length) * 100);

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
