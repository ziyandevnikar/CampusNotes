import { InjectionToken } from '@angular/core';
import { environment } from '../../environments/environment';

/** Base URL of the Flask API, without a trailing slash. Inject this; never hardcode the URL. */
export const API_URL = new InjectionToken<string>('API_URL', {
  providedIn: 'root',
  factory: () => environment.apiUrl.replace(/\/+$/, ''),
});
