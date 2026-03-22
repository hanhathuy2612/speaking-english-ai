import { CommonModule, DOCUMENT } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterModule,
  RouterOutlet,
} from '@angular/router';
import { filter } from 'rxjs';
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
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);

  /** Mobile hamburger drawer */
  readonly mobileMenuOpen = signal(false);

  constructor() {
    this.router.events
      .pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => {
        this.mobileMenuOpen.set(false);
        this.syncConversationScrollLock();
      });
  }

  toggleMobileMenu(): void {
    this.mobileMenuOpen.update((open) => !open);
  }

  closeMobileMenu(): void {
    this.mobileMenuOpen.set(false);
  }

  ngOnInit(): void {
    this.syncConversationScrollLock();
    if (this.auth.isLoggedIn()) {
      this.account.refreshFromServer().subscribe({ error: () => {} });
    }
  }

  /** Lock outer page scroll on conversation; inner .chat-area scrolls only. */
  private syncConversationScrollLock(): void {
    const lock = this.router.url.includes('/conversation');
    const root = this.document.documentElement;
    const body = this.document.body;
    if (body) {
      root.classList.toggle('conversation-route', lock);
      body.classList.toggle('conversation-route', lock);
    }
  }

  hiddenNavbar(): boolean {
    return this.router.url.includes('/conversation');
  }
}
