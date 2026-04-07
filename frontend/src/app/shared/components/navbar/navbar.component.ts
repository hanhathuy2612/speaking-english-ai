import { CommonModule } from '@angular/common';
import { Component, DOCUMENT, inject, model } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterModule } from '@angular/router';
import { AccountService } from '../../services/account.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, RouterModule, RouterLinkActive, RouterLink],
  templateUrl: './navbar.component.html',
  styleUrls: ['./navbar.component.scss'],
})
export class NavbarComponent {
  readonly auth = inject(AuthService);
  readonly account = inject(AccountService);
  private readonly document = inject(DOCUMENT);

  readonly menuOpen = model(true);

  onNavLinkClick(): void {
    if (this.isMobileViewport()) {
      this.setMenuOpen(false);
    }
  }

  toggleMobileMenu(): void {
    this.menuOpen.update((v) => !v);
  }

  closeMobileMenu(): void {
    this.setMenuOpen(false);
  }

  onLogoutClick(): void {
    this.auth.logout();
    if (this.isMobileViewport()) {
      this.setMenuOpen(false);
    }
  }

  private setMenuOpen(next: boolean): void {
    this.menuOpen.set(next);
  }

  private isMobileViewport(): boolean {
    return this.document.defaultView?.matchMedia('(max-width: 767.98px)').matches ?? false;
  }
}
