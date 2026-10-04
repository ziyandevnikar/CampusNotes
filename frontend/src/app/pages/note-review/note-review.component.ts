import { HttpErrorResponse } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { AdminService } from '../../core/admin.service';
import { errorMessage } from '../../core/api-error';
import { FileService, asPdf } from '../../core/file.service';
import { AdminNote } from '../../core/models';
import { StateViewComponent } from '../../shared/state-view.component';

type Action = 'approve' | 'reject';

@Component({
  selector: 'app-note-review',
  standalone: true,
  imports: [RouterLink, DatePipe, StateViewComponent],
  templateUrl: './note-review.component.html',
})
export class NoteReviewComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly adminApi = inject(AdminService);
  private readonly files = inject(FileService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly destroyRef = inject(DestroyRef);

  private noteId = 0;
  private previewUrl: string | null = null;

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly note = signal<AdminNote | null>(null);

  protected readonly previewLoading = signal(false);
  protected readonly previewError = signal<string | null>(null);
  protected readonly preview = signal<SafeResourceUrl | null>(null);

  protected readonly busy = signal<Action | 'open' | 'download' | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly actionError = signal<string | null>(null);

  constructor() {
    // Free the in-memory PDF when leaving the page.
    this.destroyRef.onDestroy(() => this.releasePreview());
  }

  ngOnInit(): void {
    const raw = this.route.snapshot.paramMap.get('id') ?? '';
    if (!/^[0-9]+$/.test(raw)) {
      this.loading.set(false);
      this.error.set('Note not found.');
      return;
    }
    this.noteId = Number(raw);
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.adminApi
      .get(this.noteId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (note) => {
          this.note.set(note);
          this.loading.set(false);
          this.loadPreview();
        },
        error: (err: unknown) => {
          this.error.set(errorMessage(err));
          this.loading.set(false);
        },
      });
  }

  /** Fetch the PDF (with the admin token) and show it in the browser's own PDF viewer. */
  protected loadPreview(): void {
    this.releasePreview();
    this.previewLoading.set(true);
    this.previewError.set(null);
    this.adminApi
      .pdf(this.noteId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (blob) => {
          this.previewUrl = URL.createObjectURL(asPdf(blob));
          // The URL was just created by this page from the bytes we fetched; it is safe to embed.
          this.preview.set(this.sanitizer.bypassSecurityTrustResourceUrl(this.previewUrl));
          this.previewLoading.set(false);
        },
        error: (err: unknown) => {
          this.previewError.set(errorMessage(err));
          this.previewLoading.set(false);
        },
      });
  }

  protected openPdf(): void {
    this.runFile('open', this.files.open(this.adminApi.pdf(this.noteId)));
  }

  protected downloadPdf(note: AdminNote): void {
    this.runFile('download', this.files.download(this.adminApi.pdf(this.noteId), note.title));
  }

  protected moderate(note: AdminNote, action: Action): void {
    if (this.busy() !== null) {
      return;
    }
    const verb = action === 'approve' ? 'Approve' : 'Reject';
    if (!confirm(`${verb} "${note.title}"? This cannot be undone.`)) {
      return;
    }

    this.busy.set(action);
    this.notice.set(null);
    this.actionError.set(null);

    const request$ = action === 'approve' ? this.adminApi.approve(note.id) : this.adminApi.reject(note.id);
    request$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.note.set({ ...note, status: action === 'approve' ? 'approved' : 'rejected' });
        this.notice.set(
          action === 'approve'
            ? 'Note approved. It is now visible to students.'
            : 'Note rejected. It stays hidden from students.',
        );
        this.busy.set(null);
      },
      error: (err: unknown) => {
        this.actionError.set(errorMessage(err));
        this.busy.set(null);
        if (err instanceof HttpErrorResponse && err.status === 400) {
          this.load(); // already processed elsewhere: show its real status
        }
      },
    });
  }

  private runFile(kind: 'open' | 'download', action$: ReturnType<FileService['open']>): void {
    if (this.busy() !== null) {
      return;
    }
    this.busy.set(kind);
    this.actionError.set(null);
    action$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      error: (err: unknown) => {
        this.actionError.set(errorMessage(err));
        this.busy.set(null);
      },
      complete: () => this.busy.set(null),
    });
  }

  private releasePreview(): void {
    if (this.previewUrl) {
      URL.revokeObjectURL(this.previewUrl);
      this.previewUrl = null;
    }
    this.preview.set(null);
  }
}
