import { Component, DestroyRef, OnInit, WritableSignal, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Observable } from 'rxjs';

import { errorMessage } from '../core/api-error';
import { AcademicService } from '../core/academic.service';
import { Course, Semester, Subject, Unit } from '../core/models';

type Level = 'course' | 'semester' | 'subject' | 'unit';

/**
 * Four linked drop-downs (Course > Semester > Subject > Unit) filled from the API.
 * Emits the chosen unit id, or null while the choice is incomplete.
 */
@Component({
  selector: 'app-unit-picker',
  standalone: true,
  template: `
    <div class="picker">
      <div class="field">
        <label for="pk-course">Course</label>
        <select id="pk-course" #course (change)="onCourse(course.value)" [disabled]="locked() || courses().length === 0">
          <option value="" [selected]="courseId() === null">{{ placeholder('course', courses().length, 'courses') }}</option>
          @for (c of courses(); track c.id) {
            <option [value]="c.id" [selected]="c.id === courseId()">{{ c.name }}</option>
          }
        </select>
      </div>

      <div class="field">
        <label for="pk-semester">Semester</label>
        <select id="pk-semester" #semester (change)="onSemester(semester.value)" [disabled]="locked() || semesters().length === 0">
          <option value="" [selected]="semesterId() === null">{{ placeholder('semester', semesters().length, 'semesters') }}</option>
          @for (s of semesters(); track s.id) {
            <option [value]="s.id" [selected]="s.id === semesterId()">Semester {{ s.number }}</option>
          }
        </select>
      </div>

      <div class="field">
        <label for="pk-subject">Subject</label>
        <select id="pk-subject" #subject (change)="onSubject(subject.value)" [disabled]="locked() || subjects().length === 0">
          <option value="" [selected]="subjectId() === null">{{ placeholder('subject', subjects().length, 'subjects') }}</option>
          @for (s of subjects(); track s.id) {
            <option [value]="s.id" [selected]="s.id === subjectId()">{{ s.name }}</option>
          }
        </select>
      </div>

      <div class="field">
        <label for="pk-unit">Unit</label>
        <select id="pk-unit" #unit (change)="onUnit(unit.value)" [disabled]="locked() || units().length === 0">
          <option value="" [selected]="unitId() === null">{{ placeholder('unit', units().length, 'units') }}</option>
          @for (u of units(); track u.id) {
            <option [value]="u.id" [selected]="u.id === unitId()">{{ u.title }}</option>
          }
        </select>
      </div>
    </div>
    @if (error()) {
      <p class="field-error" role="alert">{{ error() }}</p>
    }
  `,
})
export class UnitPickerComponent implements OnInit {
  private readonly academic = inject(AcademicService);
  private readonly destroyRef = inject(DestroyRef);

  /** Disable the drop-downs (for example while uploading). */
  readonly locked = input(false);
  readonly unitSelected = output<number | null>();

  readonly courses = signal<Course[]>([]);
  readonly semesters = signal<Semester[]>([]);
  readonly subjects = signal<Subject[]>([]);
  readonly units = signal<Unit[]>([]);

  readonly courseId = signal<number | null>(null);
  readonly semesterId = signal<number | null>(null);
  readonly subjectId = signal<number | null>(null);
  readonly unitId = signal<number | null>(null);

  private readonly loadingLevel = signal<Level | null>(null);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.fetch('course', this.academic.courses(), this.courses, () => true);
  }

  placeholder(level: Level, count: number, plural: string): string {
    if (this.loadingLevel() === level) {
      return `Loading ${plural}…`;
    }
    if (level === 'course') {
      return count === 0 ? 'No courses available' : 'Select course';
    }
    const parent = { semester: this.courseId(), subject: this.semesterId(), unit: this.subjectId() }[level];
    if (parent === null) {
      return `Select ${plural === 'semesters' ? 'a course' : plural === 'subjects' ? 'a semester' : 'a subject'} first`;
    }
    return count === 0 ? `No ${plural} found` : `Select ${level}`;
  }

  onCourse(value: string): void {
    const id = this.toId(value);
    this.courseId.set(id);
    this.resetBelow('semester');
    if (id !== null) {
      this.fetch('semester', this.academic.semesters(id), this.semesters, () => this.courseId() === id);
    }
  }

  onSemester(value: string): void {
    const id = this.toId(value);
    this.semesterId.set(id);
    this.resetBelow('subject');
    if (id !== null) {
      this.fetch('subject', this.academic.subjects(id), this.subjects, () => this.semesterId() === id);
    }
  }

  onSubject(value: string): void {
    const id = this.toId(value);
    this.subjectId.set(id);
    this.resetBelow('unit');
    if (id !== null) {
      this.fetch('unit', this.academic.units(id), this.units, () => this.subjectId() === id);
    }
  }

  onUnit(value: string): void {
    const id = this.toId(value);
    this.unitId.set(id);
    this.unitSelected.emit(id);
  }

  /** Clear every level from `from` downwards and tell the parent the choice is incomplete. */
  private resetBelow(from: 'semester' | 'subject' | 'unit'): void {
    this.error.set(null);
    this.loadingLevel.set(null);
    if (from === 'semester') {
      this.semesters.set([]);
      this.semesterId.set(null);
    }
    if (from === 'semester' || from === 'subject') {
      this.subjects.set([]);
      this.subjectId.set(null);
    }
    this.units.set([]);
    this.unitId.set(null);
    this.unitSelected.emit(null);
  }

  private fetch<T>(level: Level, request: Observable<T[]>, target: WritableSignal<T[]>, stillCurrent: () => boolean): void {
    this.error.set(null);
    this.loadingLevel.set(level);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (list) => {
        if (stillCurrent()) {
          target.set(list);
          this.loadingLevel.set(null);
        }
      },
      error: (err: unknown) => {
        if (stillCurrent()) {
          this.error.set(errorMessage(err));
          this.loadingLevel.set(null);
        }
      },
    });
  }

  private toId(value: string): number | null {
    return /^[0-9]+$/.test(value) ? Number(value) : null;
  }
}
