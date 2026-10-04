import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from './api.config';
import { Course, Semester, Subject, Unit } from './models';

/** Course -> Semester -> Subject -> Unit (public browse endpoints). */
@Injectable({ providedIn: 'root' })
export class AcademicService {
  private readonly http = inject(HttpClient);
  private readonly api = inject(API_URL);

  courses(): Observable<Course[]> {
    return this.http.get<Course[]>(`${this.api}/courses`);
  }

  semesters(courseId: number): Observable<Semester[]> {
    return this.http.get<Semester[]>(`${this.api}/semesters`, {
      params: new HttpParams().set('course_id', courseId),
    });
  }

  subjects(semesterId: number): Observable<Subject[]> {
    return this.http.get<Subject[]>(`${this.api}/subjects`, {
      params: new HttpParams().set('semester_id', semesterId),
    });
  }

  units(subjectId: number): Observable<Unit[]> {
    return this.http.get<Unit[]>(`${this.api}/units`, {
      params: new HttpParams().set('subject_id', subjectId),
    });
  }
}
