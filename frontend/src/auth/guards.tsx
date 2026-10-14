import { Navigate, Outlet, useLocation, useSearchParams } from "react-router";
import { nextPath } from "../features/auth/LoginPage";
import { useAuth } from "./AuthContext";

/** Pages behind the login: a logged-out visitor goes to /login and comes back here afterwards. */
export function RequireAuth() {
  const { user } = useAuth();
  const { pathname, search } = useLocation();
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(pathname + search)}`} replace />;
  return <Outlet />;
}

/** Admin pages: a learner who types the address lands on the home page. The server checks the role
 * again on every call (require_admin), this only keeps the menu and the routes in step with it. */
export function RequireAdmin() {
  const { user } = useAuth();
  if (user?.role !== "admin") return <Navigate to="/" replace />;
  return <Outlet />;
}

/** Login and sign-up: already logged in, go where the link pointed (or home). */
export function GuestOnly() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  if (user) return <Navigate to={nextPath(params)} replace />;
  return <Outlet />;
}
