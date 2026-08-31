import { Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './auth.component.html',
  styleUrl: './auth.component.scss',
})
export class AuthComponent {
  readonly mode = signal<'in' | 'up'>('in');
  readonly isSignUp = computed(() => this.mode() === 'up');
  readonly title = computed(() => (this.isSignUp() ? 'Keep your rebuild.' : 'Welcome back.'));
  readonly note = computed(() =>
    this.isSignUp()
      ? 'One account holds every scan, preview and published site. We ask for it now so your preview link survives a closed tab.'
      : 'Sign in to pick up a preview, publish a rebuild, or start a new scan.');
  readonly cta = computed(() => (this.isSignUp() ? 'Create account' : 'Sign in'));

  form = { email: '', password: '', site: '' };

  /** TODO: POST /api/auth/sign-in | /api/auth/sign-up */
  submit(): void {}
}
