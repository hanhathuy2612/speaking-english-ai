import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, AUTH_EXPIRED } from "../api/http";
import type { User } from "../api/types";

type Auth = {
  /** undefined while the first /api/auth/me is pending, null when logged out. */
  user: User | null | undefined;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (user: User | null) => void;
};

const AuthContext = createContext<Auth | null>(null);

/** Who is logged in, shared by every page (docs/features/accounts.md). The login itself is an HttpOnly
 * cookie the page never reads: the server is asked once on load, and again only after a login. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    api<User>("/api/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
    const expired = () => setUser(null);
    window.addEventListener(AUTH_EXPIRED, expired);
    return () => window.removeEventListener(AUTH_EXPIRED, expired);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const u = await api<User>("/api/auth/login", { body: { email, password } });
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(async () => {
    await api("/api/auth/logout", { body: {} }).catch(() => {});
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, login, logout, setUser }), [user, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Auth {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth outside AuthProvider");
  return auth;
}

/** The logged-in user, for pages that are only shown after login. */
export function useUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error("useUser without a logged-in user");
  return user;
}
