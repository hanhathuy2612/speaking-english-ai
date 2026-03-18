import { Component, ChangeDetectionStrategy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { form, FormField, required, email } from '@angular/forms/signals';
import { AuthService } from '../../shared/services/auth.service';

interface LoginData {
  email: string;
  password: string;
}

@Component({
  selector: 'app-login',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormField, RouterLink],
  styleUrls: ['./login.component.scss'],
  templateUrl: './login.component.html',
})
export class LoginComponent {
  loginModel = signal<LoginData>({
    email: 'withuwe021@gmail.com',
    password: 'withuwe021@gmail.com',
  });

  loginForm = form(this.loginModel, (schemaPath) => {
    required(schemaPath.email, { message: 'Email is required' });
    email(schemaPath.email, { message: 'Enter a valid email address' });
    required(schemaPath.password, { message: 'Password is required' });
  });

  loading = signal(false);
  error = signal('');

  constructor(
    private auth: AuthService,
    private router: Router,
  ) {}

  onSubmit(event: Event): void {
    event.preventDefault();
    if (this.loginForm().invalid()) return;

    const { email, password } = this.loginModel();
    this.loading.set(true);
    this.error.set('');

    this.auth.login(email, password).subscribe({
      next: () => this.router.navigateByUrl('/topics'),
      error: (e) => {
        this.error.set(e.error?.detail ?? 'Login failed');
        this.loading.set(false);
      },
    });
  }
}
