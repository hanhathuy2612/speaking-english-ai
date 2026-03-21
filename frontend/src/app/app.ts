import { CommonModule } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterModule, RouterOutlet } from '@angular/router';
import { AccountService } from './shared/services/account.service';
import { AuthService } from './shared/services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterModule, RouterLinkActive, RouterLink, RouterOutlet],
  templateUrl: './app.html',
  styleUrls: ['./app.scss'],
})
export class App implements OnInit {
  auth = inject(AuthService);
  account = inject(AccountService);

  ngOnInit(): void {
    if (this.auth.isLoggedIn()) {
      this.account.refreshFromServer().subscribe({ error: () => {} });
    }
  }
}
