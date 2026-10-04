import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, map, tap } from 'rxjs';

import { API_URL } from './api.config';
import { UserFacingError } from './api-error';
import { LoginResponse, MessageResponse, Role } from './models';

const TOKEN_KEY = 'campusnotes.token';
const ROLE_KEY = 'campusnotes.role';

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // storage can be unavailable (private mode, blocked cookies)
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, value);
    }
  } catch {
    // Ignore: the session then simply lasts until the tab is closed.
  }
}

/** Expiry time of a JWT in milliseconds, or null if it cannot be read. */
function tokenExpiry(token: string): number | null {
  try {
    const part = token.split('.')[1];
    if (!part) {
      return null;
    }
    const base64 = part.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded)) as { exp?: unknown };
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

function isUsable(token: string): boolean {
  const expiry = tokenExpiry(token);
  return expiry !== null && expiry > Date.now();
}

/**
 * Holds the login session.
 *
 * The JWT and role are kept in localStorage so a refresh keeps you logged in.
 * That is acceptable for this MVP but not XSS-proof; the Flask backend remains
 * the real authorization layer, so editing these values only changes what the UI shows.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly api = inject(API_URL);

  private readonly tokenSignal = signal<string | null>(null);
  private readonly roleSignal = signal<Role | null>(null);

  readonly role = this.roleSignal.asReadonly();
  readonly isLoggedIn = computed(() => this.tokenSignal() !== null);

  constructor() {
    const token = readStorage(TOKEN_KEY);
    const role = readStorage(ROLE_KEY);
    if (token && (role === 'student' || role === 'admin') && isUsable(token)) {
      this.tokenSignal.set(token);
      this.roleSignal.set(role);
    } else {
      this.clear();
    }
  }

  /** The token to send, or null. Clears the session if the token has expired. Call from guards/interceptors, not templates. */
  currentToken(): string | null {
    const token = this.tokenSignal();
    if (token !== null && !isUsable(token)) {
      this.clear();
      return null;
    }
    return token;
  }

  isAuthenticated(): boolean {
    return this.currentToken() !== null;
  }

  /** Where this user lands after login. */
  homeRoute(): string {
    return this.roleSignal() === 'admin' ? '/admin' : '/dashboard';
  }

  register(name: string, email: string, password: string): Observable<MessageResponse> {
    return this.http.post<MessageResponse>(`${this.api}/register`, { name, email, password });
  }

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.api}/login`, { email, password }).pipe(
      map((res) => {
        const validRole = res?.role === 'student' || res?.role === 'admin';
        if (!res || typeof res.token !== 'string' || !res.token || !validRole) {
          throw new UserFacingError('Unexpected response from the server. Please try again.');
        }
        return res;
      }),
      tap((res) => {
        writeStorage(TOKEN_KEY, res.token);
        writeStorage(ROLE_KEY, res.role);
        this.tokenSignal.set(res.token);
        this.roleSignal.set(res.role);
      }),
    );
  }

  /** Clear the session and go to the login page. */
  logout(reason?: 'expired'): void {
    this.clear();
    void this.router.navigate(['/login'], { queryParams: reason ? { reason } : undefined });
  }

  private clear(): void {
    writeStorage(TOKEN_KEY, null);
    writeStorage(ROLE_KEY, null);
    this.tokenSignal.set(null);
    this.roleSignal.set(null);
  }
}
