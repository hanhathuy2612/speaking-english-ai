import { type ReactNode, useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router";
import { api } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { ChatIcon, MapIcon, MenuIcon, MoreIcon, RepeatIcon, UserIcon, WaveIcon } from "./Icons";
import { Sheet } from "./Sheet";

const NAV = [
  { to: "/", label: "Phòng tập" },
  { to: "/review", label: "Ôn tập" },
  { to: "/roadmap", label: "Lộ trình" },
  { to: "/sounds", label: "Phát âm" },
  { to: "/fluency", label: "Nói dài" },
  { to: "/check", label: "Kiểm tra" },
  { to: "/history", label: "Tiến bộ" },
];
const ADMIN = { to: "/admin", label: "Quản trị" }; // only for the admin role; active on every /admin page

/** Bottom tab bar on phones (styles/base.css, .tabbar): the four daily pages, the rest under "Thêm". */
const TABS = [
  { to: "/roadmap", label: "Lộ trình", icon: <MapIcon /> },
  { to: "/", label: "Luyện", icon: <ChatIcon size={22} /> },
  { to: "/review", label: "Ôn tập", icon: <RepeatIcon /> },
  { to: "/sounds", label: "Phát âm", icon: <WaveIcon /> },
];

/**
 * Top bar shared by every page. `children` go between the brand and the navigation.
 * On narrow screens the links collapse into a menu button (styles/base.css, .nav-toggle),
 * and on phones they move to a tab bar at the bottom.
 */
export function AppBar({ children }: { children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const { user } = useAuth();
  const nav = user?.role === "admin" ? [...NAV, ADMIN] : NAV;
  const more = [...nav.filter((n) => !TABS.some((t) => t.to === n.to)), { to: "/account", label: "Tài khoản" }];
  const wrap = useRef<HTMLDivElement>(null);
  const current =
    nav.find((n) => n.to === pathname || (n.to === "/admin" && pathname.startsWith("/admin/")))?.label ?? "Menu";
  const [due, setDue] = useState(0);
  const [moreOpen, setMoreOpen] = useState(false);

  // Review cards due today, shown as a badge (refreshed on every page change).
  useEffect(() => {
    let live = true;
    api<{ due: number }>("/api/review/count")
      .then((d) => live && setDue(d.due))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [pathname]);

  useEffect(() => {
    setOpen(false);
    setMoreOpen(false);
  }, [pathname]);

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
          aria-label={`Menu, đang ở: ${current}${due ? `, ${due} thẻ ôn đến hạn` : ""}`}
          onClick={() => setOpen((o) => !o)}
        >
          <MenuIcon />
          <span className="nav-toggle-label">{current}</span>
          {due > 0 && (
            <span className="nav-badge" aria-hidden>
              {due}
            </span>
          )}
        </button>
        <nav id="main-nav" className={`nav${open ? " open" : ""}`} aria-label="Các trang">
          {nav.map((n) => (
            // NavLink sets aria-current="page" on the active route, which the CSS highlights.
            <NavLink key={n.to} to={n.to} end={n.to !== "/admin"} className="btn btn-ghost btn-sm">
              {n.label}
              {n.to === "/review" && due > 0 && (
                <span className="nav-badge" aria-label={`${due} thẻ đến hạn`}>
                  {due}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </div>
      {user && (
        <NavLink to="/account" className="btn btn-ghost btn-sm account-link" aria-label={`Tài khoản: ${user.name}`}>
          <UserIcon />
          <span className="account-name">{user.name}</span>
        </NavLink>
      )}

      <nav className="tabbar" aria-label="Các trang chính">
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to} end className="tab">
            {t.icon}
            <span>{t.label}</span>
            {t.to === "/review" && due > 0 && (
              <span className="nav-badge" aria-label={`${due} thẻ đến hạn`}>
                {due}
              </span>
            )}
          </NavLink>
        ))}
        <button
          className={`tab${more.some((n) => n.to === pathname) || pathname.startsWith("/admin/") ? " on" : ""}`}
          aria-haspopup="dialog"
          onClick={() => setMoreOpen(true)}
        >
          <MoreIcon />
          <span>Thêm</span>
        </button>
      </nav>
      <Sheet open={moreOpen} onClose={() => setMoreOpen(false)} title="Thêm">
        <nav className="more-nav" aria-label="Các trang khác">
          {more.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to !== "/admin"} className="btn">
              {n.label}
            </NavLink>
          ))}
        </nav>
      </Sheet>
    </header>
  );
}
