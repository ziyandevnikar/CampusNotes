import { Injectable } from '@angular/core';
import { Observable, map, tap } from 'rxjs';

import { UserFacingError } from './api-error';

/** Always treat the bytes as a PDF so the browser never renders them as anything else. */
export function asPdf(blob: Blob): Blob {
  return new Blob([blob], { type: 'application/pdf' });
}

/**
 * Opening and saving PDFs. The API needs an Authorization header for some
 * downloads, which a plain link cannot send, so the PDF is fetched with
 * HttpClient (token added by the interceptor) and handed to the browser as a blob.
 */
@Injectable({ providedIn: 'root' })
export class FileService {
  /**
   * Show the PDF in a new tab using the browser's own PDF viewer.
   * The tab must be opened inside the click handler (before the async download),
   * otherwise pop-up blockers stop it; so call this directly from a click.
   */
  open(source: Observable<Blob>): Observable<void> {
    const tab = window.open('', '_blank');
    if (tab) {
      try {
        tab.document.title = 'CampusNotes';
        tab.document.body.textContent = 'Loading PDF…';
      } catch {
        // Cosmetic only.
      }
    }
    return source.pipe(
      map((blob) => {
        if (!tab || tab.closed) {
          throw new UserFacingError(
            'Your browser blocked the new tab. Allow pop-ups for this site, or use Download.',
          );
        }
        // Not revoked on purpose: the viewer may reload it; it is freed when this page closes.
        tab.location.href = URL.createObjectURL(asPdf(blob));
      }),
      tap({ error: () => tab?.close() }),
    );
  }

  /** Save the PDF to disk. */
  download(source: Observable<Blob>, title: string): Observable<void> {
    return source.pipe(
      map((blob) => {
        const url = URL.createObjectURL(asPdf(blob));
        const link = document.createElement('a');
        link.href = url;
        link.download = this.fileName(title);
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }),
    );
  }

  private fileName(title: string): string {
    const safe = title
      .replace(/[^A-Za-z0-9 _-]+/g, '')
      .trim()
      .replace(/\s+/g, '_')
      .slice(0, 80);
    return `${safe || 'note'}.pdf`;
  }
}
