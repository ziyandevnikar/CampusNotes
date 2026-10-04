import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, ParamMap, Params, RouterLink } from '@angular/router';
import { BehaviorSubject, Observable, catchError, combineLatest, forkJoin, map, of, switchMap, tap } from 'rxjs';

import { errorMessage } from '../../core/api-error';
import { AcademicService } from '../../core/academic.service';
import { Course, Semester, Subject, Unit } from '../../core/models';
import { StateViewComponent } from '../../shared/state-view.component';

type RouteLink = (string | number)[];

interface Choice {
  id: number;
  label: string;
  link: RouteLink;
  query?: Params;
}

interface Crumb {
  label: string;
  link: RouteLink;
}

interface View {
  title: string;
  subtitle: string;
  emptyText: string;
  choices: Choice[];
  crumbs: Crumb[];
  allNotes: Params | null;
}

interface Loaded {
  courses: Course[];
  semesters: Semester[] | null;
  subjects: Subject[] | null;
  units: Unit[] | null;
}

interface Result {
  view: View | null;
  error: string | null;
}

const fail = (message: string): Result => ({ view: null, error: message });

/**
 * One screen for the whole Course > Semester > Subject > Unit walk.
 * The URL decides which level is shown, so the browser's Back button works.
 * Everything displayed comes from the API; nothing about the hierarchy is hardcoded.
 */
@Component({
  selector: 'app-browse',
  standalone: true,
  imports: [RouterLink, StateViewComponent],
  templateUrl: './browse.component.html',
})
export class BrowseComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly academic = inject(AcademicService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly reload$ = new BehaviorSubject<void>(undefined);

  protected readonly loading = signal(true);
  protected readonly loadingText = signal('Loading courses…');
  protected readonly error = signal<string | null>(null);
  protected readonly view = signal<View | null>(null);
  protected readonly hasNoChoices = computed(() => this.view()?.choices.length === 0);

  ngOnInit(): void {
    combineLatest([this.route.paramMap, this.reload$])
      .pipe(
        tap(([params]) => {
          this.loading.set(true);
          this.error.set(null);
          this.loadingText.set(
            params.has('subjectId')
              ? 'Loading units…'
              : params.has('semesterId')
                ? 'Loading subjects…'
                : params.has('courseId')
                  ? 'Loading semesters…'
                  : 'Loading courses…',
          );
        }),
        switchMap(([params]) => this.loadView(params)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.view.set(result.view);
        this.error.set(result.error);
        this.loading.set(false);
      });
  }

  protected reload(): void {
    this.reload$.next();
  }

  private loadView(params: ParamMap): Observable<Result> {
    const ids = ['courseId', 'semesterId', 'subjectId'].map((key) => {
      const raw = params.get(key);
      return raw === null ? null : /^[0-9]+$/.test(raw) ? Number(raw) : NaN;
    });
    if (ids.some((id) => id !== null && Number.isNaN(id))) {
      return of(fail('This link is not valid.'));
    }
    const [courseId, semesterId, subjectId] = ids;

    return forkJoin({
      courses: this.academic.courses(),
      semesters: this.optional(courseId, (id) => this.academic.semesters(id)),
      subjects: this.optional(semesterId, (id) => this.academic.subjects(id)),
      units: this.optional(subjectId, (id) => this.academic.units(id)),
    }).pipe(
      map((data) => this.buildView(courseId, semesterId, subjectId, data)),
      catchError((err: unknown) => of(fail(errorMessage(err)))),
    );
  }

  private optional<T>(id: number | null, request: (id: number) => Observable<T>): Observable<T | null> {
    return id === null ? of(null) : request(id);
  }

  private buildView(courseId: number | null, semesterId: number | null, subjectId: number | null, data: Loaded): Result {
    const crumbs: Crumb[] = [{ label: 'Courses', link: ['/browse'] }];

    if (courseId === null) {
      return {
        error: null,
        view: {
          title: 'Choose your course',
          subtitle: 'Start with the programme you study.',
          emptyText: 'No courses found.',
          choices: data.courses.map((c) => ({ id: c.id, label: c.name, link: ['/browse', c.id] })),
          crumbs,
          allNotes: null,
        },
      };
    }

    const course = data.courses.find((c) => c.id === courseId);
    if (!course) {
      return fail('Course not found.');
    }
    crumbs.push({ label: course.name, link: ['/browse', courseId] });
    const semesters = data.semesters ?? [];

    if (semesterId === null) {
      return {
        error: null,
        view: {
          title: `${course.name}: choose a semester`,
          subtitle: 'Select the semester you want notes for.',
          emptyText: 'No semesters found.',
          choices: semesters.map((s) => ({ id: s.id, label: `Semester ${s.number}`, link: ['/browse', courseId, s.id] })),
          crumbs,
          allNotes: null,
        },
      };
    }

    const semester = semesters.find((s) => s.id === semesterId);
    if (!semester) {
      return fail('Semester not found.');
    }
    crumbs.push({ label: `Semester ${semester.number}`, link: ['/browse', courseId, semesterId] });
    const subjects = data.subjects ?? [];

    if (subjectId === null) {
      return {
        error: null,
        view: {
          title: `Semester ${semester.number}: choose a subject`,
          subtitle: `Subjects in ${course.name}, semester ${semester.number}.`,
          emptyText: 'No subjects found.',
          choices: subjects.map((s) => ({ id: s.id, label: s.name, link: ['/browse', courseId, semesterId, s.id] })),
          crumbs,
          allNotes: null,
        },
      };
    }

    const subject = subjects.find((s) => s.id === subjectId);
    if (!subject) {
      return fail('Subject not found.');
    }
    crumbs.push({ label: subject.name, link: ['/browse', courseId, semesterId, subjectId] });
    const units = data.units ?? [];

    return {
      error: null,
      view: {
        title: `${subject.name}: choose a unit`,
        subtitle: 'Pick a unit to see its notes.',
        emptyText: 'No units found.',
        choices: units.map((u) => ({
          id: u.id,
          label: u.title,
          link: ['/notes'],
          query: { subject_id: subjectId, unit_id: u.id, ctx: `${subject.name} › ${u.title}` },
        })),
        crumbs,
        allNotes: { subject_id: subjectId, ctx: subject.name },
      },
    };
  }
}
