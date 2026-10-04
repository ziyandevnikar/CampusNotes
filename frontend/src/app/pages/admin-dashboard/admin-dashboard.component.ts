import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { AdminService } from '../../core/admin.service';
import { errorMessage } from '../../core/api-error';
import { StateViewComponent } from '../../shared/state-view.component';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [RouterLink, StateViewComponent],
  templateUrl: './admin-dashboard.component.html',
})
export class AdminDashboardComponent implements OnInit {
  private readonly adminApi = inject(AdminService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly denied = inject(ActivatedRoute).snapshot.queryParamMap.get('reason') === 'denied';
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  /** Live number of notes waiting for review (from the API, never hardcoded). */
  protected readonly pendingCount = signal(0);

  ngOnInit(): void {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.adminApi
      .pending()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (notes) => {
          this.pendingCount.set(notes.length);
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.error.set(errorMessage(err));
          this.loading.set(false);
        },
      });
  }
}
