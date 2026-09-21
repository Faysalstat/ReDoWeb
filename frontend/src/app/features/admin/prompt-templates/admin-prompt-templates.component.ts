import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ButtonComponent } from '../../../shared/ui/button/button.component';
import { SpinnerComponent } from '../../../shared/ui/spinner/spinner.component';
import { AdminApiService } from '../core/admin-api.service';
import { AdminPromptTemplateRow } from '../core/admin-api.models';

const KNOWN_CATEGORIES = ['business', 'service', 'portfolio'] as const;
const NEW_CATEGORY_OPTION = '__new__';

/** Upload/enable/disable/delete design-strategy prompt templates. The
 * prompt TEXT always stays a plain .txt file in backend/prompts/ -- this
 * page only manages the upload + active-state metadata, per the user's
 * explicit direction (category dropdown, backend writes the file into the
 * prompts folder with the category baked into the filename). */
@Component({
  selector: 'app-admin-prompt-templates',
  standalone: true,
  imports: [FormsModule, DatePipe, SpinnerComponent, ButtonComponent],
  templateUrl: './admin-prompt-templates.component.html',
})
export class AdminPromptTemplatesComponent implements OnInit {
  readonly knownCategories = KNOWN_CATEGORIES;
  readonly newCategoryOption = NEW_CATEGORY_OPTION;

  readonly templates = signal<AdminPromptTemplateRow[]>([]);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  readonly selectedCategory = signal<string>(KNOWN_CATEGORIES[0]);
  readonly customCategory = signal('');
  readonly templateName = signal('');
  readonly selectedFile = signal<File | null>(null);
  readonly uploading = signal(false);
  readonly uploadError = signal('');
  readonly togglingFilename = signal<string | null>(null);

  constructor(private readonly api: AdminApiService) {}

  ngOnInit(): void {
    this.load();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile.set(input.files?.[0] ?? null);
  }

  effectiveCategory(): string {
    return this.selectedCategory() === NEW_CATEGORY_OPTION ? this.customCategory().trim() : this.selectedCategory();
  }

  upload(): void {
    this.uploadError.set('');
    const category = this.effectiveCategory();
    const name = this.templateName().trim();
    const file = this.selectedFile();

    if (!category) {
      this.uploadError.set('Category is required.');
      return;
    }
    if (!name) {
      this.uploadError.set('Template name is required.');
      return;
    }
    if (!file) {
      this.uploadError.set('Choose a .txt file to upload.');
      return;
    }

    this.uploading.set(true);
    this.api.uploadPromptTemplate(category, name, file).subscribe({
      next: () => {
        this.uploading.set(false);
        this.templateName.set('');
        this.customCategory.set('');
        this.selectedFile.set(null);
        this.load();
      },
      error: (err) => {
        this.uploading.set(false);
        this.uploadError.set(err?.error?.detail ?? 'Upload failed.');
      },
    });
  }

  toggleActive(row: AdminPromptTemplateRow): void {
    this.togglingFilename.set(row.filename);
    this.api.setPromptTemplateActive(row.filename, !row.is_active).subscribe({
      next: () => {
        this.togglingFilename.set(null);
        this.load();
      },
      error: () => {
        this.togglingFilename.set(null);
        this.errorMessage.set(`Failed to update ${row.filename}.`);
      },
    });
  }

  deleteTemplate(row: AdminPromptTemplateRow): void {
    if (!confirm(`Delete ${row.filename}? This cannot be undone.`)) return;
    this.api.deletePromptTemplate(row.filename).subscribe({
      next: () => this.load(),
      error: () => this.errorMessage.set(`Failed to delete ${row.filename}.`),
    });
  }

  private load(): void {
    this.loading.set(true);
    this.errorMessage.set('');
    this.api.listPromptTemplates().subscribe({
      next: (res) => {
        this.templates.set(res.items);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load prompt templates.');
        this.loading.set(false);
      },
    });
  }
}
