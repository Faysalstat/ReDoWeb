import { Component, input } from '@angular/core';
import { SafeResourceUrl } from '@angular/platform-browser';

/** A chunky sticker-style browser window around a preview iframe. Toolbar
 * buttons are projected via `[toolbar-actions]`. `fullscreen` pins it over
 * the whole viewport. */
@Component({
  selector: 'pg-browser-frame',
  standalone: true,
  host: { style: 'display: block' },
  template: `
    <div class="bf" [class.bf--full]="fullscreen()">
      <div class="bf__bar">
        <span class="bf__dots" aria-hidden="true"><i></i><i></i><i></i></span>
        <span class="bf__url">{{ url() }}</span>
        <span class="bf__actions"><ng-content select="[toolbar-actions]" /></span>
      </div>
      <iframe class="bf__frame" [src]="previewUrl()" [title]="iframeTitle()"></iframe>
    </div>
  `,
  styles: [
    `
      .bf {
        background: var(--pg-card);
        border: var(--pg-bw) solid var(--pg-fg);
        border-radius: var(--pg-radius-md);
        box-shadow: 8px 8px 0 0 var(--pg-fg);
        overflow: hidden;
      }
      .bf--full {
        position: fixed;
        inset: 0;
        z-index: 200;
        display: flex;
        flex-direction: column;
        border-radius: 0;
        border: 0;
        box-shadow: none;
      }
      .bf__bar {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 12px;
        background: var(--pg-amber-soft);
        border-bottom: var(--pg-bw) solid var(--pg-fg);
      }
      .bf__dots {
        display: flex;
        gap: 6px;
        flex: none;
      }
      .bf__dots i {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        border: var(--pg-bw) solid var(--pg-fg);
        background: var(--pg-pink);
      }
      .bf__dots i:nth-child(2) {
        background: var(--pg-amber);
      }
      .bf__dots i:nth-child(3) {
        background: var(--pg-mint);
      }
      .bf__url {
        flex: 1;
        min-width: 0;
        padding: 5px 14px;
        border: var(--pg-bw) solid var(--pg-fg);
        border-radius: var(--pg-radius-full);
        background: var(--pg-card);
        font-size: var(--pg-text-xs);
        font-weight: 600;
        color: var(--pg-muted-fg);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .bf__actions {
        display: flex;
        gap: 6px;
        flex: none;
      }
      .bf__frame {
        display: block;
        width: 100%;
        height: 640px;
        border: 0;
        background: #fff;
      }
      .bf--full .bf__frame {
        flex: 1;
        height: auto;
      }
      @media (max-width: 640px) {
        .bf {
          box-shadow: 4px 4px 0 0 var(--pg-fg);
        }
        .bf__frame {
          height: 520px;
        }
      }
    `,
  ],
})
export class PgBrowserFrameComponent {
  readonly url = input('');
  readonly previewUrl = input.required<SafeResourceUrl>();
  readonly fullscreen = input(false);
  readonly iframeTitle = input('Website preview');
}
