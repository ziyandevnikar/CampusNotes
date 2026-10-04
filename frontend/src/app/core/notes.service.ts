import { HttpClient, HttpEvent, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from './api.config';
import { MessageResponse, Note, NotesFilter } from './models';

@Injectable({ providedIn: 'root' })
export class NotesService {
  private readonly http = inject(HttpClient);
  private readonly api = inject(API_URL);

  /** Approved notes only (the backend enforces this). */
  list(filter: NotesFilter = {}): Observable<Note[]> {
    let params = new HttpParams();
    const q = filter.q?.trim();
    if (q) {
      params = params.set('q', q);
    }
    if (filter.subjectId) {
      params = params.set('subject_id', filter.subjectId);
    }
    if (filter.unitId) {
      params = params.set('unit_id', filter.unitId);
    }
    return this.http.get<Note[]>(`${this.api}/notes`, { params });
  }

  get(id: number): Observable<Note> {
    return this.http.get<Note>(`${this.api}/notes/${id}`);
  }

  /** The PDF itself. Note: the backend counts every call as one download. */
  pdf(id: number): Observable<Blob> {
    return this.http.get(`${this.api}/notes/${id}/download`, { responseType: 'blob' });
  }

  /**
   * Upload a PDF as multipart/form-data. The uploader is taken from the JWT by the
   * backend, so no user id is sent. Emits progress events, then the response.
   */
  upload(form: FormData): Observable<HttpEvent<MessageResponse>> {
    return this.http.post<MessageResponse>(`${this.api}/notes`, form, {
      reportProgress: true,
      observe: 'events',
    });
  }
}
