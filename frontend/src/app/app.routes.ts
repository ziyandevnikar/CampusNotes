import { Routes } from '@angular/router';

import { guestGuard, homeGuard, roleGuard } from './core/guards';

const browse = () => import('./pages/browse/browse.component').then((m) => m.BrowseComponent);

export const routes: Routes = [
  // "/" sends visitors to Login, students to their dashboard, admins to theirs.
  { path: '', pathMatch: 'full', canActivate: [homeGuard], children: [] },

  // Public
  {
    path: 'login',
    canActivate: [guestGuard],
    title: 'Log in · CampusNotes',
    loadComponent: () => import('./pages/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'register',
    canActivate: [guestGuard],
    title: 'Register · CampusNotes',
    loadComponent: () => import('./pages/register/register.component').then((m) => m.RegisterComponent),
  },

  // Student area
  {
    path: '',
    canActivate: [roleGuard('student')],
    children: [
      {
        path: 'dashboard',
        title: 'Dashboard · CampusNotes',
        loadComponent: () =>
          import('./pages/student-dashboard/student-dashboard.component').then((m) => m.StudentDashboardComponent),
      },
      { path: 'browse', title: 'Browse · CampusNotes', loadComponent: browse },
      { path: 'browse/:courseId', title: 'Browse · CampusNotes', loadComponent: browse },
      { path: 'browse/:courseId/:semesterId', title: 'Browse · CampusNotes', loadComponent: browse },
      { path: 'browse/:courseId/:semesterId/:subjectId', title: 'Browse · CampusNotes', loadComponent: browse },
      {
        path: 'notes',
        title: 'Notes · CampusNotes',
        loadComponent: () => import('./pages/notes-list/notes-list.component').then((m) => m.NotesListComponent),
      },
      {
        path: 'notes/:id',
        title: 'Note · CampusNotes',
        loadComponent: () => import('./pages/note-detail/note-detail.component').then((m) => m.NoteDetailComponent),
      },
      {
        path: 'upload',
        title: 'Upload note · CampusNotes',
        loadComponent: () => import('./pages/upload-note/upload-note.component').then((m) => m.UploadNoteComponent),
      },
    ],
  },

  // Admin area
  {
    path: 'admin',
    canActivate: [roleGuard('admin')],
    children: [
      {
        path: '',
        pathMatch: 'full',
        title: 'Admin · CampusNotes',
        loadComponent: () =>
          import('./pages/admin-dashboard/admin-dashboard.component').then((m) => m.AdminDashboardComponent),
      },
      {
        path: 'pending',
        title: 'Pending notes · CampusNotes Admin',
        loadComponent: () => import('./pages/pending-notes/pending-notes.component').then((m) => m.PendingNotesComponent),
      },
      {
        path: 'notes/:id',
        title: 'Review note · CampusNotes Admin',
        loadComponent: () => import('./pages/note-review/note-review.component').then((m) => m.NoteReviewComponent),
      },
    ],
  },

  { path: '**', redirectTo: '' },
];
