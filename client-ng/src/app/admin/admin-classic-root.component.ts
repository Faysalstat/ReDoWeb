import { Component, ViewEncapsulation } from '@angular/core';

import { AdminShellComponent } from './shell/admin-shell.component';

/** client-ng only: the admin panel is copied from frontend/ unchanged, so it
 * still needs frontend/'s classic stylesheet. This wrapper loads that sheet
 * (scoped under .classic-admin by scripts/scope-admin-css.js, unencapsulated so
 * it reaches every admin page) and only for the lazy /admin chunk, plus a
 * small sheet that undoes Tailwind's preflight inside the admin panel. */
@Component({
  selector: 'app-admin-classic-root',
  standalone: true,
  imports: [AdminShellComponent],
  encapsulation: ViewEncapsulation.None,
  // Order matters: undo Tailwind's reset first, then the classic rules on top.
  styleUrls: ['./admin-preflight-undo.css', './admin-classic.css'],
  template: `<div class="classic-admin"><app-admin-shell /></div>`,
})
export class AdminClassicRootComponent {}
