import { HttpEventType } from '@angular/common/http';
import { Component, DestroyRef, ElementRef, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { errorMessage } from '../../core/api-error';
import { NotesService } from '../../core/notes.service';
import { UnitPickerComponent } from '../../shared/unit-picker.component';

// Limits mirror the backend (routes/notes_routes.py and config.py).
const MAX_TITLE = 200;
const MAX_DESCRIPTION = 5000;
const MAX_FILE_BYTES = 10 * 1024 * 1024;

interface FieldErrors {
  title?: string;
  description?: string;
  unit?: string;
  file?: string;
}

@Component({
  selector: 'app-upload-note',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, UnitPickerComponent],
  templateUrl: './upload-note.component.html',
})
export class UploadNoteComponent {
  private readonly notesApi = inject(NotesService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fileInput = viewChild<ElementRef<HTMLInputElement>>('fileInput');

  protected readonly maxTitle = MAX_TITLE;
  protected readonly maxDescription = MAX_DESCRIPTION;

  protected readonly form = new FormGroup({
    title: new FormControl('', { nonNullable: true }),
    description: new FormControl('', { nonNullable: true }),
  });

  protected readonly unitId = signal<number | null>(null);
  protected readonly file = signal<File | null>(null);
  protected readonly fieldErrors = signal<FieldErrors>({});
  protected readonly error = signal<string | null>(null);
  protected readonly uploading = signal(false);
  protected readonly progress = signal(0);
  protected readonly done = signal(false);

  protected onUnit(id: number | null): void {
    this.unitId.set(id);
    this.clearError('unit');
  }

  protected onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const chosen = input.files && input.files.length > 0 ? input.files[0] : null;
    this.file.set(chosen);
    this.clearError('file');
    if (chosen) {
      const problem = this.fileProblem(chosen);
      if (problem) {
        this.fieldErrors.update((errors) => ({ ...errors, file: problem }));
      }
    }
  }

  protected clearError(field: keyof FieldErrors): void {
    if (this.fieldErrors()[field]) {
      this.fieldErrors.update((errors) => ({ ...errors, [field]: undefined }));
    }
  }

  protected formatSize(bytes: number): string {
    return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  protected submit(): void {
    if (this.uploading()) {
      return;
    }
    this.error.set(null);

    const { title, description } = this.form.getRawValue();
    const cleanTitle = title.trim();
    const cleanDescription = description.trim();
    const file = this.file();
    const unitId = this.unitId();

    const errors: FieldErrors = {};
    if (!cleanTitle) {
      errors.title = 'Title is required.';
    } else if (cleanTitle.length > MAX_TITLE) {
      errors.title = `Title must be at most ${MAX_TITLE} characters.`;
    }
    if (cleanDescription.length > MAX_DESCRIPTION) {
      errors.description = `Description must be at most ${MAX_DESCRIPTION} characters.`;
    }
    if (unitId === null) {
      errors.unit = 'Select a course, semester, subject and unit.';
    }
    if (!file) {
      errors.file = 'Choose a PDF file.';
    } else {
      const problem = this.fileProblem(file);
      if (problem) {
        errors.file = problem;
      }
    }
    this.fieldErrors.set(errors);
    if (Object.keys(errors).length > 0 || !file || unitId === null) {
      return;
    }

    // No uploader id is sent: the backend takes the uploader from the JWT.
    const data = new FormData();
    data.append('title', cleanTitle);
    data.append('description', cleanDescription);
    data.append('unit_id', String(unitId));
    data.append('file', file, file.name);

    this.uploading.set(true);
    this.progress.set(0);
    this.notesApi
      .upload(data)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress && event.total) {
            this.progress.set(Math.round((100 * event.loaded) / event.total));
          } else if (event.type === HttpEventType.Response) {
            this.uploading.set(false);
            this.done.set(true);
          }
        },
        error: (err: unknown) => {
          this.uploading.set(false);
          this.error.set(errorMessage(err));
        },
      });
  }

  /** Back to an empty form after a successful upload. */
  protected uploadAnother(): void {
    this.form.reset();
    this.file.set(null);
    this.unitId.set(null);
    this.fieldErrors.set({});
    this.error.set(null);
    this.progress.set(0);
    this.done.set(false); // the form (and unit picker) are created fresh
  }

  protected clearFile(): void {
    this.file.set(null);
    this.clearError('file');
    const input = this.fileInput();
    if (input) {
      input.nativeElement.value = '';
    }
  }

  private fileProblem(file: File): string | null {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      return 'Only PDF files are allowed.';
    }
    if (file.size === 0) {
      return 'The selected file is empty.';
    }
    if (file.size > MAX_FILE_BYTES) {
      return 'File is too large (maximum 10 MB).';
    }
    return null;
  }
}
