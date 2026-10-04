import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';
import { Role } from './models';

/*
 * These guards only decide what the UI shows. They are NOT security:
 * the Flask backend checks the token and role on every request.
 */

/** Allow only logged-in users with the given role. */
export const roleGuard =
  (role: Role): CanActivateFn =>
  () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    if (!auth.isAuthenticated()) {
      return router.createUrlTree(['/login']);
    }
    if (auth.role() !== role) {
      return router.createUrlTree([auth.homeRoute()], { queryParams: { reason: 'denied' } });
    }
    return true;
  };

/** Login/Register are for visitors only; logged-in users go to their dashboard. */
export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  return auth.isAuthenticated() ? inject(Router).createUrlTree([auth.homeRoute()]) : true;
};

/** "/" sends everyone to the right place. */
export const homeGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  return inject(Router).createUrlTree([auth.isAuthenticated() ? auth.homeRoute() : '/login']);
};
