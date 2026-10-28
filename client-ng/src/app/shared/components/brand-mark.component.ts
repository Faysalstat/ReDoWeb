import { Component } from '@angular/core';
import { LucideAngularModule, Sparkles } from 'lucide-angular';

/** Secondary mark (sidebar, footer): gradient tile with Sparkles + name. */
@Component({
  selector: 'app-brand-mark',
  standalone: true,
  imports: [LucideAngularModule],
  template: `
    <span class="flex items-center gap-2">
      <span class="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-purple-400 flex items-center justify-center">
        <lucide-icon [img]="Sparkles" class="w-4 h-4 text-white" />
      </span>
      <span class="font-display font-bold text-lg">ReDoWebs</span>
    </span>
  `,
})
export class BrandMarkComponent {
  protected readonly Sparkles = Sparkles;
}
