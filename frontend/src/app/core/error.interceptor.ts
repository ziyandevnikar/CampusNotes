import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Observable, catchError, from, map, switchMap, throwError } from 'rxjs';

import { API_URL } from './api.config';
import { AuthService } from './auth.service';

/** Parse a JSON error body that arrived as a Blob (PDF downloads ask for blobs). */
function parseBlobBody(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/**
 * Central place for the two things every failed API call needs:
 *  - a 401 on a protected call means the session is gone: clear it and go to Login;
 *  - error bodies of blob downloads are turned back into normal JSON bodies.
 * Login/register 401s (wrong password) are NOT a session problem and are left alone.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const api = inject(API_URL);
  const auth = inject(AuthService);

  return next(req).pipe(
    catchError((err: unknown): Observable<never> => {
      if (!(err instanceof HttpErrorResponse)) {
        return throwError(() => err);
      }

      const isAuthForm = /\/(login|register)$/.test(req.url);
      if (req.url.startsWith(api) && err.status === 401 && !isAuthForm) {
        auth.logout('expired');
      }

      if (err.error instanceof Blob) {
        return from(err.error.text()).pipe(
          map((text) => parseBlobBody(text)),
          switchMap((body) =>
            throwError(
              () =>
                new HttpErrorResponse({
                  error: body,
                  headers: err.headers,
                  status: err.status,
                  statusText: err.statusText,
                  url: err.url ?? undefined,
                }),
            ),
          ),
        );
      }
      return throwError(() => err);
    }),
  );
};
