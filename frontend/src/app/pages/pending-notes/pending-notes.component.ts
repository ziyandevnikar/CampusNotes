import { HttpErrorResponse } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';

import { AdminService } from '../../core/admin.service';
import { errorMessage } from '../../core/api-error';
import { AdminNote } from '../../core/models';
import { StateViewComponent } from '../../shared/state-view.component';

type Action = 'approve' | 'reject';

@Component({
  selector: 'app-pending-notes',
  standalone: true,
  imports: [RouterLink, DatePipe, StateViewComponent],
  templateUrl: './pending-notes.component.html',
})
export class PendingNotesComponent implements OnInit {
  private readonly adminApi = inject(AdminService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly notes = signal<AdminNote[]>([]);
  protected readonly notice = signal<string | null>(null);
  protected readonly actionError = signal<string | null>(null);
  /** The note and action currently being sent; while set, every action button is disabled. */
  protected readonly busy = signal<{ id: number; action: Action } | null>(null);

  ngOnInit(): void {
    this.load();
  }

  protected load(silent = false): void {
    if (!silent) {
      this.loading.set(true);
    }
    this.error.set(null);
    this.adminApi
      .pending()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (notes) => {
          this.notes.set(notes);
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.error.set(errorMessage(err));
          this.loading.set(false);
        },
      });
  }

  protected moderate(note: AdminNote, action: Action): void {
    if (this.busy() !== null) {
      return; // prevents double clicks and overlapping requests
    }
    const verb = action === 'approve' ? 'Approve' : 'Reject';
    if (!confirm(`${verb} "${note.title}"? This cannot be undone.`)) {
      return;
    }

    this.busy.set({ id: note.id, action });
    this.notice.set(null);
    this.actionError.set(null);

    const request$ = action === 'approve' ? this.adminApi.approve(note.id) : this.adminApi.reject(note.id);
    request$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.notes.update((list) => list.filter((n) => n.id !== note.id));
        this.notice.set(`"${note.title}" was ${action === 'approve' ? 'approved and is now visible to students' : 'rejected and stays hidden'}.`);
        this.busy.set(null);
      },
      error: (err: unknown) => {
        this.actionError.set(errorMessage(err));
        this.busy.set(null);
        if (err instanceof HttpErrorResponse && (err.status === 400 || err.status === 404)) {
          this.load(true); // someone else already handled it: refresh the queue
        }
      },
    });
  }

  protected isBusy(note: AdminNote, action: Action): boolean {
    const current = this.busy();
    return current !== null && current.id === note.id && current.action === action;
  }
}
