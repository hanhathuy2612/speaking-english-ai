import { type ReactNode, useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router";
import { ChatIcon, MapIcon, MenuIcon, MoreIcon, RepeatIcon, WaveIcon } from "./Icons";
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

/** Bottom tab bar on phones (styles/base.css, .tabbar): the four daily pages, the rest under "Thêm". */
const TABS = [
  { to: "/roadmap", label: "Lộ trình", icon: <MapIcon /> },
  { to: "/", label: "Luyện", icon: <ChatIcon size={22} /> },
  { to: "/review", label: "Ôn tập", icon: <RepeatIcon /> },
  { to: "/sounds", label: "Phát âm", icon: <WaveIcon /> },
];
const MORE = NAV.filter((n) => !TABS.some((t) => t.to === n.to));

/**
 * Top bar shared by every page. `children` go between the brand and the navigation.
 * On narrow screens the links collapse into a menu button (styles/base.css, .nav-toggle),
 * and on phones they move to a tab bar at the bottom.
 */
export function AppBar({ children }: { children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const wrap = useRef<HTMLDivElement>(null);
  const current = NAV.find((n) => n.to === pathname)?.label ?? "Menu";
  const [due, setDue] = useState(0);
  const [more, setMore] = useState(false);

  // Review cards due today, shown as a badge (refreshed on every page change).
  useEffect(() => {
    let live = true;
    fetch("/api/review/count")
      .then((r) => (r.ok ? r.json() : { due: 0 }))
      .then((d: { due: number }) => live && setDue(d.due))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [pathname]);

  useEffect(() => {
    setOpen(false);
    setMore(false);
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
          {due > 0 && <span className="nav-badge" aria-hidden>{due}</span>}
        </button>
        <nav id="main-nav" className={`nav${open ? " open" : ""}`} aria-label="Các trang">
          {NAV.map((n) => (
            // NavLink sets aria-current="page" on the active route, which the CSS highlights.
            <NavLink key={n.to} to={n.to} end className="btn btn-ghost btn-sm">
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
          className={`tab${MORE.some((n) => n.to === pathname) ? " on" : ""}`}
          aria-haspopup="dialog"
          onClick={() => setMore(true)}
        >
          <MoreIcon />
          <span>Thêm</span>
        </button>
      </nav>
      <Sheet open={more} onClose={() => setMore(false)} title="Thêm">
        <nav className="more-nav" aria-label="Các trang khác">
          {MORE.map((n) => (
            <NavLink key={n.to} to={n.to} end className="btn">
              {n.label}
            </NavLink>
          ))}
        </nav>
      </Sheet>
    </header>
  );
}
