import { HttpClient } from '@angular/common/http';
import { Injectable, computed, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { API_BASE_URL } from './api-config';
import { UserOut } from './redowebs-api.models';

const TOKEN_STORAGE_KEY = 'redowebs_token';
const USER_STORAGE_KEY = 'redowebs_user';

/** Session state lives in sessionStorage (token + user), restored
 * synchronously on construction -- no bootstrap network call needed. Login
 * is a full-page redirect to the backend's Google OAuth2 authorize endpoint;
 * the backend does the code exchange server-side and redirects back to
 * /auth/callback with the issued JWT (see auth-callback.component.ts). */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly _token = signal<string | null>(sessionStorage.getItem(TOKEN_STORAGE_KEY));
  readonly currentUser = signal<UserOut | null>(this.restoreUser());
  readonly isAuthenticated = computed(() => this._token() !== null);

  constructor(private readonly http: HttpClient) {}

  getAccessToken(): string | null {
    return this._token();
  }

  startGoogleLogin(): void {
    window.location.href = `${API_BASE_URL}/api/v1/auth/google/authorize`;
  }

  /** Called by AuthCallbackComponent once the backend redirect delivers a
   * token. Persists it, then fetches the profile to populate currentUser. */
  completeLogin(token: string): Observable<UserOut> {
    this._token.set(token);
    sessionStorage.setItem(TOKEN_STORAGE_KEY, token);

    return this.http.get<UserOut>(`${API_BASE_URL}/api/v1/auth/me`).pipe(
      tap((user) => {
        this.currentUser.set(user);
        sessionStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
      })
    );
  }

  /** No backend call -- there's no server-side session to revoke with a
   * single long-lived JWT, so logout just clears local state. */
  logout(): void {
    this._token.set(null);
    this.currentUser.set(null);
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    sessionStorage.removeItem(USER_STORAGE_KEY);
  }

  private restoreUser(): UserOut | null {
    const raw = sessionStorage.getItem(USER_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as UserOut;
    } catch {
      return null;
    }
  }
}
