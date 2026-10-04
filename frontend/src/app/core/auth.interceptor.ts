import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { API_URL } from './api.config';
import { AuthService } from './auth.service';

/** Adds `Authorization: Bearer <JWT>` to every request that goes to the Flask API. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const api = inject(API_URL);
  if (!req.url.startsWith(api)) {
    return next(req); // never leak the token to other sites
  }
  const token = inject(AuthService).currentToken();
  return token ? next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })) : next(req);
};
