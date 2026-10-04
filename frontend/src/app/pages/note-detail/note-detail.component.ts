import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { BehaviorSubject, catchError, combineLatest, map, of, switchMap, tap } from 'rxjs';

import { errorMessage } from '../../core/api-error';
import { FileService } from '../../core/file.service';
import { Note } from '../../core/models';
import { NotesService } from '../../core/notes.service';
import { StateViewComponent } from '../../shared/state-view.component';

@Component({
  selector: 'app-note-detail',
  standalone: true,
  imports: [RouterLink, StateViewComponent],
  templateUrl: './note-detail.component.html',
})
export class NoteDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly notesApi = inject(NotesService);
  private readonly files = inject(FileService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly reload$ = new BehaviorSubject<void>(undefined);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly note = signal<Note | null>(null);
  protected readonly busy = signal<'open' | 'download' | null>(null);
  protected readonly actionError = signal<string | null>(null);

  ngOnInit(): void {
    combineLatest([this.route.paramMap, this.reload$])
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.error.set(null);
          this.actionError.set(null);
        }),
        switchMap(([params]) => {
          const raw = params.get('id') ?? '';
          if (!/^[0-9]+$/.test(raw)) {
            return of({ note: null as Note | null, error: 'Note not found.' as string | null });
          }
          return this.notesApi.get(Number(raw)).pipe(
            map((note) => ({ note: note as Note | null, error: null as string | null })),
            catchError((err: unknown) => of({ note: null as Note | null, error: errorMessage(err) as string | null })),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.note.set(result.note);
        this.error.set(result.error);
        this.loading.set(false);
      });
  }

  protected reload(): void {
    this.reload$.next();
  }

  protected open(note: Note): void {
    this.run('open', this.files.open(this.notesApi.pdf(note.id)));
  }

  protected download(note: Note): void {
    this.run('download', this.files.download(this.notesApi.pdf(note.id), note.title));
  }

  private run(kind: 'open' | 'download', action$: ReturnType<FileService['open']>): void {
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
}
