import type { ReactNode } from "react";
import { Link, NavLink } from "react-router";
import { ChatIcon } from "./Icons";

const NAV = [
  { to: "/", label: "Phòng tập" },
  { to: "/history", label: "Tiến bộ" },
  { to: "/bench", label: "Đo nhận dạng" },
];

/** Top bar shared by every page. `children` go between the brand and the navigation. */
export function AppBar({ children }: { children?: ReactNode }) {
  return (
    <header className="appbar">
      <Link className="brand" to="/">
        <span className="brand-mark" aria-hidden>
          <ChatIcon />
        </span>
        <span className="brand-name">Phòng tập phỏng vấn</span>
      </Link>
      {children}
      <div className="appbar-spacer" />
      <nav className="nav">
        {NAV.map((n) => (
          // NavLink sets aria-current="page" on the active route, which the CSS highlights.
          <NavLink key={n.to} to={n.to} end className="btn btn-ghost btn-sm">
            {n.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
