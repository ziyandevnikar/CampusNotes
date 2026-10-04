import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { API_URL } from './api.config';
import { AdminNote, MessageResponse } from './models';

/** Moderation endpoints. All of them need an admin token; the backend enforces it. */
@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly http = inject(HttpClient);
  private readonly api = inject(API_URL);

  pending(): Observable<AdminNote[]> {
    return this.http
      .get<{ notes: AdminNote[] }>(`${this.api}/admin/notes/pending`)
      .pipe(map((res) => res.notes ?? []));
  }

  get(id: number): Observable<AdminNote> {
    return this.http.get<AdminNote>(`${this.api}/admin/notes/${id}`);
  }

  /** The PDF of a note in any status, for review (not counted as a download). */
  pdf(id: number): Observable<Blob> {
    return this.http.get(`${this.api}/admin/notes/${id}/download`, { responseType: 'blob' });
  }

  approve(id: number): Observable<MessageResponse> {
    return this.http.patch<MessageResponse>(`${this.api}/admin/notes/${id}/approve`, {});
  }

  reject(id: number): Observable<MessageResponse> {
    return this.http.patch<MessageResponse>(`${this.api}/admin/notes/${id}/reject`, {});
  }
}
