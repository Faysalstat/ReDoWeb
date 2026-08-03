import { Component, computed, input } from '@angular/core';
import { SafeResourceUrl } from '@angular/platform-browser';

@Component({
  selector: 'app-browser-frame',
  standalone: true,
  host: { class: 'block' },
  template: `
    <div [class]="containerClasses()">
      <div [class]="toolbarClasses()">
        <div class="flex min-w-0 items-center gap-2">
          <span class="h-3 w-3 shrink-0 rounded-full bg-red-400"></span>
          <span class="h-3 w-3 shrink-0 rounded-full bg-amber-400"></span>
          <span class="h-3 w-3 shrink-0 rounded-full bg-emerald-400"></span>
          @if (fullscreen()) {
            <span class="ml-2 truncate text-xs text-ink-muted">{{ url() }}</span>
          } @else {
            <span
              class="ml-3 flex-1 truncate rounded-md border border-white/10 bg-canvas-elevated px-3 py-1 text-xs text-ink-muted"
            >
              {{ url() }}
            </span>
          }
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <ng-content select="[toolbar-actions]" />
        </div>
      </div>
      <iframe [src]="previewUrl()" [class]="iframeClasses()" [title]="iframeTitle()"></iframe>
    </div>
  `,
})
export class BrowserFrameComponent {
  readonly url = input('');
  readonly previewUrl = input.required<SafeResourceUrl>();
  readonly fullscreen = input(false);
  readonly iframeTitle = input('Website preview');

  protected readonly containerClasses = computed(() =>
    this.fullscreen()
      ? 'fixed inset-0 z-50 flex flex-col bg-canvas'
      : 'overflow-hidden rounded-2xl border border-white/10 bg-white/5 shadow-card backdrop-blur-xl'
  );

  protected readonly toolbarClasses = computed(() =>
    this.fullscreen()
      ? 'flex items-center justify-between gap-3 border-b border-white/10 bg-canvas-elevated/90 px-4 py-3 backdrop-blur'
      : 'flex items-center gap-2 border-b border-white/10 bg-canvas-elevated/50 px-4 py-3'
  );

  protected readonly iframeClasses = computed(() =>
    this.fullscreen() ? 'w-full flex-1 bg-white' : 'h-[640px] w-full bg-white'
  );
}
