export type Role = 'student' | 'admin';
export type NoteStatus = 'pending' | 'approved' | 'rejected';

export interface LoginResponse {
  token: string;
  role: Role;
}

export interface MessageResponse {
  message: string;
}

export interface Course {
  id: number;
  name: string;
}

export interface Semester {
  id: number;
  number: number;
}

export interface Subject {
  id: number;
  name: string;
}

export interface Unit {
  id: number;
  title: string;
}

/** A note as students see it (GET /notes, GET /notes/<id>). Always approved. */
export interface Note {
  id: number;
  title: string;
  description: string | null;
  subject: string;
  unit: string;
  file_url: string;
}

/** A note as admins see it (GET /admin/notes/...). Any status. */
export interface AdminNote {
  id: number;
  title: string;
  description: string | null;
  unit_id: number;
  uploader_id: number;
  file_type: string;
  status: NoteStatus;
  created_at: string | null;
  download_count: number;
  subject: string;
  unit: string;
  file_url: string;
}

export interface NotesFilter {
  q?: string;
  subjectId?: number | null;
  unitId?: number | null;
}
