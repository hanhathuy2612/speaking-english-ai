import { NavLink } from "react-router";
import "../../styles/admin.css";

/** Tabs between the admin pages (docs/features/accounts.md, docs/features/content-admin.md). */
export function AdminNav() {
  return (
    <nav className="admin-nav" aria-label="Quản trị">
      <NavLink to="/admin/users" className="btn btn-ghost btn-sm">
        Người dùng
      </NavLink>
      <NavLink to="/admin/content" className="btn btn-ghost btn-sm">
        Nội dung bài học
      </NavLink>
    </nav>
  );
}
