import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AmbientBackgroundComponent } from './shared/ui/ambient-background/ambient-background.component';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, AmbientBackgroundComponent],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  protected readonly title = signal('frontend');
}
