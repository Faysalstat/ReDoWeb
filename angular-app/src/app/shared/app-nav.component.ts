import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-app-nav',
  standalone: true,
  imports: [RouterLink],
  template: `
    <nav class="nav">
      <a class="nav-brand" routerLink="/dashboard">REFIT</a>
      <a routerLink="/dashboard">My sites</a>
      <a routerLink="/settings/billing">Billing</a>
      @if (context) { <span class="label">{{ context }}</span> }
      <a class="btn btn-primary" routerLink="/">New scan</a>
    </nav>
  `,
})
export class AppNavComponent {
  /** Small right-hand context line — the domain being worked on, for instance. */
  @Input() context = '';
}
