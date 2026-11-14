import { Component } from '@angular/core';
import { LogoComponent } from './logo.component';

/** Secondary mark (footer): the same brand logo, slightly larger. */
@Component({
  selector: 'app-brand-mark',
  standalone: true,
  imports: [LogoComponent],
  template: `<app-logo size="lg" />`,
})
export class BrandMarkComponent {}
