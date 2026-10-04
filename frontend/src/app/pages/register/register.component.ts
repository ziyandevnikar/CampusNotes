import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { errorMessage } from '../../core/api-error';
import { AuthService } from '../../core/auth.service';
import { EMAIL_PATTERN, fieldMessage, notBlank } from '../../core/validators';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './register.component.html',
})
export class RegisterComponent {
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly fieldMessage = fieldMessage;

  // Same limits as the backend (routes/auth_routes.py). No role field: accounts are always students.
  protected readonly form = new FormGroup({
    name: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, notBlank, Validators.maxLength(100)],
    }),
    email: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.pattern(EMAIL_PATTERN), Validators.maxLength(255)],
    }),
    password: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(6), Validators.maxLength(128)],
    }),
  });

  protected readonly submitted = signal(false);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly success = signal(false);

  protected show(control: AbstractControl): boolean {
    return control.invalid && (control.touched || this.submitted());
  }

  protected submit(): void {
    if (this.loading()) {
      return;
    }
    this.submitted.set(true);
    this.error.set(null);
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const { name, email, password } = this.form.getRawValue();
    this.loading.set(true);
    this.auth
      .register(name.trim(), email.trim(), password)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.loading.set(false);
          this.form.reset();
          this.success.set(true);
        },
        error: (err: unknown) => {
          this.loading.set(false);
          this.error.set(errorMessage(err));
        },
      });
  }
}
