import { Component, ChangeDetectionStrategy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { form, FormField, required, email, minLength } from '@angular/forms/signals';
import { AuthService } from '../../shared/services/auth.service';

interface RegisterData {
  email: string;
  username: string;
  password: string;
}

@Component({
  selector: 'app-register',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'auth-page',
  },
  imports: [CommonModule, FormField, RouterLink],
  styleUrls: ['./register.component.scss'],
  templateUrl: './register.component.html',
})
export class RegisterComponent {
  registerModel = signal<RegisterData>({
    email: '',
    username: '',
    password: '',
  });

  registerForm = form(this.registerModel, (schemaPath) => {
    required(schemaPath.email, { message: 'Email is required' });
    email(schemaPath.email, { message: 'Enter a valid email address' });
    required(schemaPath.username, { message: 'Username is required' });
    required(schemaPath.password, { message: 'Password is required' });
    minLength(schemaPath.password, 6, {
      message: 'Password must be at least 6 characters',
    });
  });

  loading = signal(false);
  error = signal('');

  constructor(
    private auth: AuthService,
    private router: Router,
  ) {}

  onSubmit(event: Event): void {
    event.preventDefault();
    if (this.registerForm().invalid()) return;

    const { email, username, password } = this.registerModel();
    this.loading.set(true);
    this.error.set('');

    this.auth.register(email, username, password).subscribe({
      next: () => this.router.navigateByUrl('/topics'),
      error: (e) => {
        this.error.set(e.error?.detail ?? 'Registration failed');
        this.loading.set(false);
      },
    });
  }
}
