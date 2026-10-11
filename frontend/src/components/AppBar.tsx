import { type ReactNode, useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router";
import { ChatIcon, MenuIcon } from "./Icons";

const NAV = [
  { to: "/", label: "Phòng tập" },
  { to: "/roadmap", label: "Lộ trình" },
  { to: "/sounds", label: "Phát âm" },
  { to: "/fluency", label: "Nói dài" },
  { to: "/check", label: "Kiểm tra" },
  { to: "/history", label: "Tiến bộ" },
];

/**
 * Top bar shared by every page. `children` go between the brand and the navigation.
 * On narrow screens the links collapse into a menu button (styles/base.css, .nav-toggle).
 */
export function AppBar({ children }: { children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const wrap = useRef<HTMLDivElement>(null);
  const current = NAV.find((n) => n.to === pathname)?.label ?? "Menu";

  useEffect(() => setOpen(false), [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onClick = (e: MouseEvent) => !wrap.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("keydown", onKey);
    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("click", onClick);
    };
  }, [open]);

  return (
    <header className="appbar">
      <Link className="brand" to="/">
        <span className="brand-mark" aria-hidden>
          <ChatIcon />
        </span>
        <span className="brand-name">Phòng tập nói</span>
      </Link>
      {children}
      <div className="appbar-spacer" />
      <div className="nav-wrap" ref={wrap}>
        <button
          className="btn btn-ghost btn-sm nav-toggle"
          aria-expanded={open}
          aria-controls="main-nav"
          aria-label={`Menu, đang ở: ${current}`}
          onClick={() => setOpen((o) => !o)}
        >
          <MenuIcon />
          <span className="nav-toggle-label">{current}</span>
        </button>
        <nav id="main-nav" className={`nav${open ? " open" : ""}`} aria-label="Các trang">
          {NAV.map((n) => (
            // NavLink sets aria-current="page" on the active route, which the CSS highlights.
            <NavLink key={n.to} to={n.to} end className="btn btn-ghost btn-sm">
              {n.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
