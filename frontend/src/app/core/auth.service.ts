import { HttpClient } from '@angular/common/http';
import { Injectable, computed, signal } from '@angular/core';
import { Observable, catchError, of, tap } from 'rxjs';

import { API_BASE_URL } from './api-config';
import { TokenResponse, UserOut } from './redowebs-api.models';

/** Holds the access token + current user in memory only (never
 * localStorage/sessionStorage) -- a page reload restores the session via
 * refreshSession(), which relies on the httpOnly refresh-token cookie
 * instead. This matches the deliberate "in-memory access token +
 * server-side-revocable refresh cookie" auth design. */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly accessToken = signal<string | null>(null);
  readonly currentUser = signal<UserOut | null>(null);
  readonly isAuthenticated = computed(() => this.currentUser() !== null);

  constructor(private readonly http: HttpClient) {}

  getAccessToken(): string | null {
    return this.accessToken();
  }

  loginWithGoogle(idToken: string): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(
        `${API_BASE_URL}/api/v1/auth/google`,
        { id_token: idToken },
        { withCredentials: true }
      )
      .pipe(tap((res) => this.applySession(res)));
  }

  /** Silently restores a session from the refresh-token cookie -- call once
   * on app startup so a page reload doesn't force the user to sign in again. */
  refreshSession(): Observable<TokenResponse | null> {
    return this.http
      .post<TokenResponse>(`${API_BASE_URL}/api/v1/auth/refresh`, {}, { withCredentials: true })
      .pipe(
        tap((res) => this.applySession(res)),
        catchError(() => {
          this.clearSession();
          return of(null);
        })
      );
  }

  logout(): Observable<void> {
    return this.http
      .post<void>(`${API_BASE_URL}/api/v1/auth/logout`, {}, { withCredentials: true })
      .pipe(
        tap(() => this.clearSession()),
        catchError(() => {
          this.clearSession();
          return of(void 0);
        })
      );
  }

  private applySession(res: TokenResponse): void {
    this.accessToken.set(res.access_token);
    this.currentUser.set(res.user);
  }

  private clearSession(): void {
    this.accessToken.set(null);
    this.currentUser.set(null);
  }
}
