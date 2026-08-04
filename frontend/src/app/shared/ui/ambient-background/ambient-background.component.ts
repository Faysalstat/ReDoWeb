import { Component } from '@angular/core';

@Component({
  selector: 'app-ambient-background',
  standalone: true,
  host: { class: 'block' },
  template: `
    <div class="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-canvas">
      <!-- Layer 1: base radial gradient -->
      <div
        class="absolute inset-0 bg-[radial-gradient(ellipse_at_top,#181832_0%,#0f0f23_50%,#0a0a17_100%)]"
      ></div>

      <!-- Layer 3: animated ambient light blobs -->
      <div
        class="animate-float absolute -top-64 left-1/2 h-[1400px] w-[900px] -translate-x-1/2 rounded-full bg-accent/25 blur-[150px]"
      ></div>
      <div
        class="animate-aurora absolute -left-40 top-1/3 h-[800px] w-[600px] rounded-full bg-accent-magenta/15 blur-[120px] [animation-delay:-8s]"
      ></div>
      <div
        class="animate-aurora absolute -right-40 top-0 h-[700px] w-[500px] rounded-full bg-accent-teal/12 blur-[100px] [animation-delay:-4s]"
      ></div>
      <div
        class="animate-float absolute bottom-0 left-1/4 h-[500px] w-[500px] rounded-full bg-accent/10 blur-[100px] [animation-delay:-5s]"
      ></div>

      <!-- Layer 2: noise texture -->
      <div class="bg-noise absolute inset-0"></div>

      <!-- Layer 4: grid overlay -->
      <div class="bg-grid absolute inset-0"></div>
    </div>
  `,
})
export class AmbientBackgroundComponent {}
