import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, RouterLinkActive, RouterLink } from '@angular/router';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterModule, RouterLinkActive, RouterLink],
  templateUrl: './app.component.html',
})
export class AppComponent {
  constructor(readonly auth: AuthService) {}

  logout(e: Event): void {
    e.preventDefault();
    this.auth.logout();
  }
}
