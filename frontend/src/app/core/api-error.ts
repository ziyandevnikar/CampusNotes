import { HttpErrorResponse } from '@angular/common/http';

/** An error whose message is already written for the user. */
export class UserFacingError extends Error {}

export interface ErrorMessageOptions {
  /** Message to show for a 401 instead of the generic "session expired" text (used by the login form). */
  unauthorized?: string;
  fallback?: string;
}

/** The backend's own `{"error": "..."}` text, if it sent a short, plain one. */
function serverMessage(err: HttpErrorResponse): string | null {
  const body: unknown = err.error;
  if (body && typeof body === 'object' && 'error' in body) {
    const text = (body as { error: unknown }).error;
    if (typeof text === 'string' && text.trim() && text.length <= 300) {
      return text.trim();
    }
  }
  return null;
}

/**
 * Turn any thrown value into a short, human-readable message.
 * Server error bodies are only shown for 4xx responses; a 5xx never exposes
 * server text (which could be a stack trace in debug mode).
 */
export function errorMessage(err: unknown, options: ErrorMessageOptions = {}): string {
  if (err instanceof UserFacingError) {
    return err.message;
  }
  if (err instanceof HttpErrorResponse) {
    const server = serverMessage(err);
    switch (err.status) {
      case 0:
        return 'Unable to connect to server.';
      case 400:
        return server ?? 'The request was not valid. Please check your input.';
      case 401:
        return options.unauthorized ?? 'Session expired. Please log in again.';
      case 403:
        return 'Access denied.';
      case 404:
        return server ?? 'Not found.';
      case 409:
        return server ?? 'That conflicts with existing data.';
      case 413:
        return server ?? 'The file is too large.';
      case 503:
        return 'The service is temporarily unavailable. Please try again shortly.';
      default:
        return err.status >= 500
          ? 'Something went wrong on the server. Please try again.'
          : (server ?? options.fallback ?? 'Something went wrong. Please try again.');
    }
  }
  return options.fallback ?? 'Something went wrong. Please try again.';
}
