import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-public-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="nav">
      <a class="nav-brand" routerLink="/">REFIT</a>
      <a routerLink="/" fragment="how">How it works</a>
      <a routerLink="/pricing" routerLinkActive="active" ariaCurrentWhenActive="page">Pricing</a>
      <a routerLink="/dashboard">Examples</a>
      <a class="btn btn-ghost" routerLink="/auth">Sign in</a>
      <a class="btn btn-primary" routerLink="/">Scan my site</a>
    </nav>
  `,
})
export class PublicNavComponent {}
