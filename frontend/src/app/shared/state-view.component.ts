import { Component, input, output } from '@angular/core';

/**
 * One consistent Loading / Error / Empty / Success wrapper for every API-driven screen.
 * Put the success content inside the tag; it is shown only when nothing else applies.
 */
@Component({
  selector: 'app-state',
  standalone: true,
  template: `
    @if (loading()) {
      <div class="state" role="status" aria-live="polite">
        <span class="spinner" aria-hidden="true"></span>
        <span>{{ loadingText() }}</span>
      </div>
    } @else if (error()) {
      <div class="alert alert-error" role="alert">
        <span>{{ error() }}</span>
        <button type="button" class="btn btn-secondary btn-small" (click)="retry.emit()">Try again</button>
      </div>
    } @else if (empty()) {
      <div class="state state-empty">
        <p>{{ emptyText() }}</p>
      </div>
    } @else {
      <ng-content />
    }
  `,
})
export class StateViewComponent {
  readonly loading = input(false);
  readonly error = input<string | null>(null);
  readonly empty = input(false);
  readonly loadingText = input('Loading…');
  readonly emptyText = input('Nothing to show.');
  readonly retry = output<void>();
}
