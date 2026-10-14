import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, AUTH_EXPIRED, forgetLogin, hasLogin, type LoginAnswer, saveLogin } from "../api/http";
import type { User } from "../api/types";

type Auth = {
  /** undefined while the first /api/auth/me is pending, null when logged out. */
  user: User | null | undefined;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (user: User | null) => void;
  /** Keep the tokens of a login answer (email link, new password) and show its user. */
  loggedIn: (answer: LoginAnswer) => void;
};

const AuthContext = createContext<Auth | null>(null);

/** Who is logged in, shared by every page (docs/features/accounts.md). The login itself is a pair of
 * JWTs kept by api/http.ts; with none stored the app shows the login page without asking the server. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    if (!hasLogin()) setUser(null);
    else
      api<User>("/api/auth/me")
        .then(setUser)
        .catch(() => setUser(null));
    const expired = () => setUser(null);
    window.addEventListener(AUTH_EXPIRED, expired);
    return () => window.removeEventListener(AUTH_EXPIRED, expired);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const u = saveLogin(await api<LoginAnswer>("/api/auth/login", { body: { email, password } }));
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(async () => {
    forgetLogin(); // stateless tokens: nothing to tell the server
    setUser(null);
  }, []);

  const loggedIn = useCallback((answer: LoginAnswer) => setUser(saveLogin(answer)), []);

  const value = useMemo(() => ({ user, login, logout, setUser, loggedIn }), [user, login, logout, loggedIn]);
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
