import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { errorMessage } from '../../core/api-error';
import { AuthService } from '../../core/auth.service';
import { fieldMessage, notBlank } from '../../core/validators';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './login.component.html',
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly fieldMessage = fieldMessage;

  protected readonly form = new FormGroup({
    email: new FormControl('', { nonNullable: true, validators: [Validators.required, notBlank] }),
    password: new FormControl('', { nonNullable: true, validators: [Validators.required] }),
  });

  protected readonly submitted = signal(false);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice: string | null;

  constructor() {
    const params = inject(ActivatedRoute).snapshot.queryParamMap;
    this.notice =
      params.get('reason') === 'expired'
        ? 'Session expired. Please log in again.'
        : params.get('registered') === '1'
          ? 'Account created. Please log in.'
          : null;
  }

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

    const { email, password } = this.form.getRawValue();
    this.loading.set(true);
    this.auth
      .login(email.trim(), password)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.loading.set(false);
          void this.router.navigateByUrl(this.auth.homeRoute());
        },
        error: (err: unknown) => {
          this.loading.set(false);
          this.error.set(errorMessage(err, { unauthorized: 'Invalid email or password.' }));
        },
      });
  }
}
