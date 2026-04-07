import { CommonModule, DOCUMENT } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { NavbarComponent } from './shared/components/navbar/navbar.component';
import { AccountService } from './shared/services/account.service';
import { AuthService } from './shared/services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, NavbarComponent, RouterOutlet],
  templateUrl: './app.html',
  styleUrls: ['./app.scss'],
})
export class App implements OnInit {
  auth = inject(AuthService);
  account = inject(AccountService);
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);

  /** Left sidebar open/close state. */
  readonly mobileMenuOpen = signal(true);

  constructor() {
    this.router.events
      .pipe(
        filter((e): e is NavigationEnd => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => {
        if (this.isMobileViewport()) {
          this.mobileMenuOpen.set(false);
        }
        this.syncConversationScrollLock();
      });
  }

  ngOnInit(): void {
    this.mobileMenuOpen.set(!this.isMobileViewport());
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

  private isMobileViewport(): boolean {
    return this.document.defaultView?.matchMedia('(max-width: 767.98px)').matches ?? false;
  }
}
