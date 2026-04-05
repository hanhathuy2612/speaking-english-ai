import {
  BreadcrumbComponent,
  BreadcrumbItem,
} from '@/app/shared/components/breadcrumb/breadcrumb.component';
import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { finalize } from 'rxjs';
import { AdminUserOut, ApiService } from '../../../shared/services/api.service';

@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [CommonModule, FormsModule, BreadcrumbComponent],
  templateUrl: './admin-users.component.html',
  styleUrls: ['./admin-users.component.scss'],
})
export class AdminUsersComponent implements OnInit {
  private readonly api = inject(ApiService);

  users = signal<AdminUserOut[]>([]);
  total = signal(0);
  page = signal(1);
  readonly pageSize = 15;
  loading = signal(false);
  error = signal('');
  savingId = signal<number | null>(null);

  readonly breadcrumbItems: readonly BreadcrumbItem[] = [
    { label: 'Admin', link: '/admin' },
    { label: 'Users', link: '/admin/users' },
  ];

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set('');
    this.api
      .adminListUsers(this.page(), this.pageSize)
      .pipe(finalize(() => this.loading.set(false)))
      .subscribe({
        next: (res) => {
          this.users.set(res.items);
          this.total.set(res.total);
        },
        error: () => this.error.set('Could not load users.'),
      });
  }

  prevPage(): void {
    if (this.page() <= 1) return;
    this.page.update((p) => p - 1);
    this.load();
  }

  nextPage(): void {
    if (this.page() * this.pageSize >= this.total()) return;
    this.page.update((p) => p + 1);
    this.load();
  }

  toggleActive(u: AdminUserOut): void {
    this.savingId.set(u.id);
    this.api
      .adminPatchUser(u.id, { is_active: !u.is_active })
      .pipe(finalize(() => this.savingId.set(null)))
      .subscribe({
        next: (updated) =>
          this.users.update((list) => list.map((x) => (x.id === updated.id ? updated : x))),
        error: () => {},
      });
  }

  toggleAdmin(u: AdminUserOut): void {
    const hasAdmin = u.roles.includes('admin');
    let nextRoles: string[];
    if (hasAdmin) {
      const withoutAdmin = u.roles.filter((r) => r !== 'admin');
      nextRoles = withoutAdmin.length > 0 ? withoutAdmin : ['user'];
    } else {
      nextRoles = [...new Set([...u.roles, 'admin'])];
    }
    this.savingId.set(u.id);
    this.api
      .adminPatchUser(u.id, { role_slugs: nextRoles })
      .pipe(finalize(() => this.savingId.set(null)))
      .subscribe({
        next: (updated) =>
          this.users.update((list) => list.map((x) => (x.id === updated.id ? updated : x))),
        error: () => {},
      });
  }
}
