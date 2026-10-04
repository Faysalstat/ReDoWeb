import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { PublicNavComponent } from '../../shared/public-nav.component';
import { SiteMockComponent } from '../../shared/site-mock.component';
import { RefitService } from '../../core/refit.service';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [FormsModule, RouterLink, PublicNavComponent, SiteMockComponent],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.scss',
})
export class LandingComponent {
  private readonly refit = inject(RefitService);
  private readonly router = inject(Router);

  url = '';
  readonly stats = [
    { value: '4:12', label: 'Median rebuild time' },
    { value: '31,904', label: 'Sites refit' },
    { value: '+2.4×', label: 'Median enquiry lift' },
  ];
  readonly steps = [
    { n: '01', title: 'You paste a URL', copy: 'We crawl what is publicly there — copy, images, structure, contact details — and keep your facts intact. Nothing is invented about your business.' },
    { n: '02', title: 'We audit, then rebuild', copy: 'Every finding is shown with its fix as it happens: layout, mobile behaviour, speed, contrast, forms that never sent anything to anyone.' },
    { n: '03', title: "You publish, or you don't", copy: 'Walk the new site page by page on desktop and phone. Keep it on your domain in one step, or close the tab and owe nothing.' },
  ];

  scan(): void {
    const url = this.url.trim();
    if (!url) return;
    this.refit.startScan(url).subscribe(({ id }) => this.router.navigate(['/scan', id]));
  }
}
