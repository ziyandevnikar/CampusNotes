import { AbstractControl, ValidationErrors } from '@angular/forms';

/** Backend email rule (routes/auth_routes.py): something@something.something, no spaces. */
export const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** Rejects values that are only whitespace. */
export function notBlank(control: AbstractControl): ValidationErrors | null {
  const value: unknown = control.value;
  return typeof value === 'string' && value.trim() === '' ? { required: true } : null;
}

/** First validation problem of a control as a sentence, or '' when it is valid. */
export function fieldMessage(control: AbstractControl, label: string): string {
  const errors = control.errors;
  if (!errors) {
    return '';
  }
  if (errors['required']) {
    return `${label} is required.`;
  }
  if (errors['pattern']) {
    return 'Enter a valid email address.';
  }
  if (errors['minlength']) {
    return `${label} must be at least ${errors['minlength'].requiredLength} characters.`;
  }
  if (errors['maxlength']) {
    return `${label} must be at most ${errors['maxlength'].requiredLength} characters.`;
  }
  return `${label} is not valid.`;
}
