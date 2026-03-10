import { Component, ChangeDetectionStrategy } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ReactiveFormsModule, FormBuilder, Validators } from "@angular/forms";
import { Router, RouterLink } from "@angular/router";
import { AuthService } from "../services/auth.service";

@Component({
  selector: "app-register",
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: "auth-page",
  },
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
  styleUrls: ["./register.component.scss"],
  templateUrl: "./register.component.html",
})
export class RegisterComponent {
  form = this.fb.nonNullable.group({
    email: ["", [Validators.required, Validators.email]],
    username: ["", Validators.required],
    password: ["", [Validators.required, Validators.minLength(6)]],
  });
  loading = false;
  error = "";

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
  ) {}

  onSubmit(): void {
    if (this.form.invalid) return;
    const { email, username, password } = this.form.getRawValue();
    this.loading = true;
    this.error = "";
    this.auth.register(email, username, password).subscribe({
      next: () => this.router.navigateByUrl("/topics"),
      error: (e) => {
        this.error = e.error?.detail ?? "Registration failed";
        this.loading = false;
      },
    });
  }
}
