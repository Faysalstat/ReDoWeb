import { Component, computed, input } from '@angular/core';
import { SafeResourceUrl } from '@angular/platform-browser';

@Component({
  selector: 'app-browser-frame',
  standalone: true,
  host: { style: 'display: block' },
  template: `
    <div [class]="containerClasses()">
      <div [class]="toolbarClasses()">
        <div class="browser-frame__dots">
          <span class="browser-frame__dot browser-frame__dot--red"></span>
          <span class="browser-frame__dot browser-frame__dot--amber"></span>
          <span class="browser-frame__dot browser-frame__dot--green"></span>
        </div>
        @if (fullscreen()) {
          <span class="browser-frame__url browser-frame__url--plain">{{ url() }}</span>
        } @else {
          <span class="browser-frame__url">{{ url() }}</span>
        }
        <div class="browser-frame__actions">
          <ng-content select="[toolbar-actions]" />
        </div>
      </div>
      <iframe [src]="previewUrl()" [class]="iframeClasses()" [title]="iframeTitle()"></iframe>
    </div>
  `,
  styles: [
    `
      .browser-frame {
        border: 1px solid var(--color-divider);
        background: var(--color-bg);
        border-radius: var(--radius-lg);
        overflow: hidden;
      }
      .browser-frame--fullscreen {
        position: fixed;
        inset: 0;
        z-index: 50;
        display: flex;
        flex-direction: column;
        border: none;
        border-radius: 0;
      }
      .browser-frame__toolbar {
        display: flex;
        align-items: center;
        gap: var(--space-3);
        padding: var(--space-2) var(--space-3);
        border-bottom: 1px solid var(--color-divider);
        background: var(--color-surface);
      }
      .browser-frame__dots {
        display: flex;
        flex: none;
        align-items: center;
        gap: 6px;
      }
      .browser-frame__dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
      }
      .browser-frame__dot--red {
        background: #ff5f57;
      }
      .browser-frame__dot--amber {
        background: #febc2e;
      }
      .browser-frame__dot--green {
        background: #28c840;
      }
      .browser-frame__url {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-size: 12px;
        color: var(--color-neutral-700);
        border: 1px solid var(--color-divider);
        padding: 4px 10px;
      }
      .browser-frame__url--plain {
        border: none;
        padding: 0;
        flex: none;
      }
      .browser-frame__actions {
        display: flex;
        flex: none;
        align-items: center;
        gap: var(--space-2);
      }
      .browser-frame__iframe {
        width: 100%;
        height: 640px;
        background: #fff;
        border: none;
        display: block;
      }
      .browser-frame__iframe--fullscreen {
        flex: 1;
        height: auto;
      }
    `,
  ],
})
export class BrowserFrameComponent {
  readonly url = input('');
  readonly previewUrl = input.required<SafeResourceUrl>();
  readonly fullscreen = input(false);
  readonly iframeTitle = input('Website preview');

  protected readonly containerClasses = computed(() =>
    this.fullscreen() ? 'browser-frame browser-frame--fullscreen' : 'browser-frame'
  );

  protected readonly toolbarClasses = computed(() => 'browser-frame__toolbar');

  protected readonly iframeClasses = computed(() =>
    this.fullscreen() ? 'browser-frame__iframe browser-frame__iframe--fullscreen' : 'browser-frame__iframe'
  );
}
