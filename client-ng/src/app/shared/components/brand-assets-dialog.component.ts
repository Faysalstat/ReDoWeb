import { Component, ElementRef, OnDestroy, computed, input, output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ImagePlus, Loader2, LucideAngularModule, RefreshCw, Trash2, X } from 'lucide-angular';

import { UiButton } from '../ui/button.directive';

export type BrandAssetRole = 'logo' | 'hero';

export interface BrandAssetsChoice {
  logo: File | null;
  hero: File | null;
  /** "I'll change them later": missing files fall back to the crawled site's images. */
  later: boolean;
}

/** Must match the backend (brand_assets_service): PNG/JPEG/WEBP only, SVG
 * deliberately excluded, 5 MB per file. The backend re-checks everything. */
const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_BYTES = 5 * 1024 * 1024;

interface Slot {
  role: BrandAssetRole;
  label: string;
  hint: string;
}

/** Pop-up opened by the home page's "Upgrade My Website": asks for the
 * logo and hero image used in the redesign. Both are required unless the
 * "change them later" box is ticked. Native <dialog> with showModal(), like
 * the history page's expired-preview notice (backdrop, focus trap, Esc). */
@Component({
  selector: 'app-brand-assets-dialog',
  standalone: true,
  imports: [FormsModule, LucideAngularModule, UiButton],
  template: `
    <dialog
      #dialog
      aria-labelledby="brand-assets-title"
      (click)="onBackdropClick($event)"
      (cancel)="onCancel($event)"
      (close)="onClosed()"
      class="w-[calc(100%-2rem)] max-w-2xl bg-transparent p-0 text-foreground backdrop:bg-black/60 backdrop:backdrop-blur-sm"
    >
      <div class="relative bg-card border border-border rounded-2xl p-6 sm:p-8 shadow-2xl text-left">
        <button
          type="button"
          aria-label="Close"
          class="absolute top-4 right-4 p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent disabled:opacity-50"
          [disabled]="submitting()"
          (click)="close()"
        >
          <lucide-icon [img]="icons.X" class="w-5 h-5" />
        </button>

        <h2 id="brand-assets-title" class="text-xl sm:text-2xl font-bold mb-2 pr-8">Add your logo and hero image</h2>
        <p class="text-sm text-muted-foreground mb-6">
          We'll build your redesign around them. PNG, JPG or WEBP, up to 5 MB each.
        </p>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          @for (slot of slots; track slot.role) {
            <div>
              <p class="text-sm font-semibold mb-2">{{ slot.label }}</p>
              <input
                #fileInput
                type="file"
                class="hidden"
                [accept]="acceptAttr"
                (change)="onFileInput(slot.role, fileInput)"
              />
              @if (previewUrl(slot.role); as url) {
                <div class="rounded-xl border border-border bg-muted/30 overflow-hidden">
                  <div class="h-40 flex items-center justify-center p-3" [class.bg-white]="slot.role === 'logo'">
                    <img [src]="url" [alt]="slot.label + ' preview'" class="max-h-full max-w-full object-contain" />
                  </div>
                  <div class="flex items-center justify-between gap-2 px-3 py-2 border-t border-border">
                    <span class="text-xs text-muted-foreground truncate">{{ file(slot.role)?.name }}</span>
                    <div class="flex gap-1 shrink-0">
                      <button
                        type="button"
                        class="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent"
                        [attr.aria-label]="'Replace ' + slot.label"
                        [disabled]="submitting()"
                        (click)="fileInput.click()"
                      >
                        <lucide-icon [img]="icons.RefreshCw" class="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        class="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        [attr.aria-label]="'Remove ' + slot.label"
                        [disabled]="submitting()"
                        (click)="clear(slot.role)"
                      >
                        <lucide-icon [img]="icons.Trash2" class="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              } @else {
                <button
                  type="button"
                  class="w-full h-[13.5rem] rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 px-4 text-center transition-colors disabled:opacity-50"
                  [class]="dragOver() === slot.role ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/60 hover:bg-accent/40'"
                  [disabled]="submitting()"
                  (click)="fileInput.click()"
                  (dragover)="onDragOver($event, slot.role)"
                  (dragleave)="dragOver.set(null)"
                  (drop)="onDrop($event, slot.role)"
                >
                  <lucide-icon [img]="icons.ImagePlus" class="w-8 h-8 text-muted-foreground" />
                  <span class="text-sm font-medium">Click or drop an image</span>
                  <span class="text-xs text-muted-foreground">{{ slot.hint }}</span>
                </button>
              }
              @if (errors()[slot.role]; as message) {
                <p class="mt-2 text-xs text-destructive">{{ message }}</p>
              }
            </div>
          }
        </div>

        <label class="mt-6 flex items-start gap-3 text-sm text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            name="brandAssetsLater"
            [ngModel]="later()"
            (ngModelChange)="later.set($event)"
            [disabled]="submitting()"
            class="mt-1 h-4 w-4 shrink-0 rounded border-input accent-green-500"
          />
          <span>
            I'll change them later, keep placeholders for now.
            <span class="block text-xs">Anything you skip uses the images from your current site.</span>
          </span>
        </label>

        @if (error()) {
          <div class="mt-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm" role="alert">{{ error() }}</div>
        }

        <div class="mt-6 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
          <button uiButton variant="outline" type="button" class="h-11 px-6 rounded-xl" [disabled]="submitting()" (click)="close()">
            Cancel
          </button>
          <button
            uiButton
            type="button"
            class="h-11 px-6 rounded-xl text-white bg-green-500 hover:bg-green-600"
            [disabled]="!canStart()"
            (click)="start()"
          >
            @if (submitting()) {
              <lucide-icon [img]="icons.Loader2" class="w-4 h-4 animate-spin" /> Starting…
            } @else {
              Start generation
            }
          </button>
        </div>
        @if (!canStart() && !submitting()) {
          <p class="mt-3 text-xs text-yellow-400 sm:text-right">Add both images, or tick the box above.</p>
        }
      </div>
    </dialog>
  `,
})
export class BrandAssetsDialogComponent implements OnDestroy {
  readonly submitting = input(false);
  readonly error = input('');
  readonly confirmed = output<BrandAssetsChoice>();

  protected readonly icons = { ImagePlus, Loader2, RefreshCw, Trash2, X };
  protected readonly acceptAttr = ACCEPTED_TYPES.join(',');
  protected readonly slots: Slot[] = [
    { role: 'logo', label: 'Logo', hint: 'A transparent PNG works best' },
    { role: 'hero', label: 'Hero image', hint: 'A wide photo, ideally 1600px or more' },
  ];

  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');

  private readonly files = signal<Record<BrandAssetRole, File | null>>({ logo: null, hero: null });
  private readonly urls = signal<Record<BrandAssetRole, string | null>>({ logo: null, hero: null });
  protected readonly errors = signal<Record<BrandAssetRole, string>>({ logo: '', hero: '' });
  protected readonly later = signal(false);
  protected readonly dragOver = signal<BrandAssetRole | null>(null);

  protected readonly canStart = computed(() => {
    if (this.submitting()) {
      return false;
    }
    const files = this.files();
    return (files.logo !== null && files.hero !== null) || this.later();
  });

  open(): void {
    const dialog = this.dialog().nativeElement;
    if (!dialog.open) {
      dialog.showModal();
    }
  }

  /** `force` is for the parent after a successful submit: the `submitting`
   * input hasn't been updated by change detection yet at that point. */
  close(force = false): void {
    if (force || !this.submitting()) {
      this.dialog().nativeElement.close();
    }
  }

  protected file(role: BrandAssetRole): File | null {
    return this.files()[role];
  }

  protected previewUrl(role: BrandAssetRole): string | null {
    return this.urls()[role];
  }

  protected onFileInput(role: BrandAssetRole, inputEl: HTMLInputElement): void {
    const file = inputEl.files?.[0] ?? null;
    inputEl.value = ''; // so picking the same file again still fires (change)
    if (file) {
      this.setFile(role, file);
    }
  }

  protected onDragOver(event: DragEvent, role: BrandAssetRole): void {
    event.preventDefault();
    this.dragOver.set(role);
  }

  protected onDrop(event: DragEvent, role: BrandAssetRole): void {
    event.preventDefault();
    this.dragOver.set(null);
    const file = event.dataTransfer?.files?.[0];
    if (file && !this.submitting()) {
      this.setFile(role, file);
    }
  }

  protected clear(role: BrandAssetRole): void {
    this.revoke(role);
    this.files.update((f) => ({ ...f, [role]: null }));
    this.urls.update((u) => ({ ...u, [role]: null }));
    this.errors.update((e) => ({ ...e, [role]: '' }));
  }

  protected start(): void {
    if (!this.canStart()) {
      return;
    }
    const files = this.files();
    this.confirmed.emit({ logo: files.logo, hero: files.hero, later: this.later() });
  }

  /** Clicking the backdrop (the <dialog> itself, outside the content box) closes it. */
  protected onBackdropClick(event: MouseEvent): void {
    if (event.target === this.dialog().nativeElement) {
      this.close();
    }
  }

  /** Esc while the upload is in flight would hide the spinner but not stop the request. */
  protected onCancel(event: Event): void {
    if (this.submitting()) {
      event.preventDefault();
    }
  }

  /** Drop the picked files once the dialog closes, so a reopened dialog starts clean. */
  protected onClosed(): void {
    this.clear('logo');
    this.clear('hero');
    this.later.set(false);
    this.dragOver.set(null);
  }

  ngOnDestroy(): void {
    this.revoke('logo');
    this.revoke('hero');
  }

  private setFile(role: BrandAssetRole, file: File): void {
    const label = role === 'logo' ? 'Logo' : 'Hero image';
    if (!ACCEPTED_TYPES.includes(file.type)) {
      this.errors.update((e) => ({ ...e, [role]: `${label}: please choose a PNG, JPG or WEBP image.` }));
      return;
    }
    if (file.size > MAX_BYTES) {
      this.errors.update((e) => ({ ...e, [role]: `${label}: the file is larger than 5 MB.` }));
      return;
    }
    this.revoke(role);
    this.files.update((f) => ({ ...f, [role]: file }));
    this.urls.update((u) => ({ ...u, [role]: URL.createObjectURL(file) }));
    this.errors.update((e) => ({ ...e, [role]: '' }));
  }

  private revoke(role: BrandAssetRole): void {
    const url = this.urls()[role];
    if (url) {
      URL.revokeObjectURL(url);
    }
  }
}
