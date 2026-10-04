import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { BehaviorSubject, catchError, combineLatest, debounceTime, distinctUntilChanged, map, of, switchMap, tap } from 'rxjs';

import { errorMessage } from '../../core/api-error';
import { FileService } from '../../core/file.service';
import { Note } from '../../core/models';
import { NotesService } from '../../core/notes.service';
import { StateViewComponent } from '../../shared/state-view.component';

function parseId(raw: string | null): number | null {
  return raw !== null && /^[0-9]+$/.test(raw) && Number(raw) > 0 ? Number(raw) : null;
}

/**
 * Notes list with search and subject/unit filters.
 * The address bar (?q=&subject_id=&unit_id=) is the single source of truth,
 * so searches can be bookmarked and the Back button works.
 */
@Component({
  selector: 'app-notes-list',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, StateViewComponent],
  templateUrl: './notes-list.component.html',
})
export class NotesListComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly notesApi = inject(NotesService);
  private readonly files = inject(FileService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly refresh$ = new BehaviorSubject<void>(undefined);
  /** The last search text this component put into the URL, to avoid overwriting what the user is typing. */
  private pushedQuery: string | null = null;

  protected readonly search = new FormControl('', { nonNullable: true });

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly notes = signal<Note[]>([]);
  protected readonly query = signal('');
  protected readonly filterLabel = signal<string | null>(null);

  /** Which button is working, as "open-<id>" / "download-<id>". */
  protected readonly busyKey = signal<string | null>(null);
  protected readonly actionError = signal<string | null>(null);

  protected readonly emptyText = computed(() =>
    this.query() || this.filterLabel()
      ? 'No notes found. Try different keywords or clear the filter.'
      : 'No notes found.',
  );

  ngOnInit(): void {
    this.search.setValue(this.route.snapshot.queryParamMap.get('q') ?? '', { emitEvent: false });

    this.search.valueChanges
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe((value) => this.applySearch(value));

    combineLatest([this.route.queryParamMap, this.refresh$])
      .pipe(
        tap(([params]) => {
          const q = params.get('q') ?? '';
          this.query.set(q);
          if (q !== this.pushedQuery && this.search.value.trim() !== q) {
            this.search.setValue(q, { emitEvent: false }); // Back/Forward navigation
          }
          const subjectId = parseId(params.get('subject_id'));
          const unitId = parseId(params.get('unit_id'));
          this.filterLabel.set(subjectId || unitId ? (params.get('ctx') ?? 'Filtered by subject / unit') : null);
          this.loading.set(true);
          this.error.set(null);
          this.actionError.set(null);
        }),
        switchMap(([params]) =>
          this.notesApi
            .list({
              q: params.get('q') ?? '',
              subjectId: parseId(params.get('subject_id')),
              unitId: parseId(params.get('unit_id')),
            })
            .pipe(
              map((notes) => ({ notes, error: null as string | null })),
              catchError((err: unknown) => of({ notes: [] as Note[], error: errorMessage(err) as string | null })),
            ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.notes.set(result.notes);
        this.error.set(result.error);
        this.loading.set(false);
      });
  }

  protected submitSearch(): void {
    const q = this.search.value.trim();
    if (q === this.query()) {
      this.refresh$.next(); // same search: just reload
    } else {
      this.applySearch(q);
    }
  }

  protected reload(): void {
    this.refresh$.next();
  }

  protected open(note: Note): void {
    this.run(`open-${note.id}`, this.files.open(this.notesApi.pdf(note.id)));
  }

  protected download(note: Note): void {
    this.run(`download-${note.id}`, this.files.download(this.notesApi.pdf(note.id), note.title));
  }

  private run(key: string, action$: ReturnType<FileService['open']>): void {
    if (this.busyKey() !== null) {
      return; // one file action at a time
    }
    this.busyKey.set(key);
    this.actionError.set(null);
    action$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      error: (err: unknown) => {
        this.actionError.set(errorMessage(err));
        this.busyKey.set(null);
      },
      complete: () => this.busyKey.set(null),
    });
  }

  private applySearch(value: string): void {
    const q = value.trim();
    this.pushedQuery = q;
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { q: q || null },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }
}
