import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { ApiError } from "../../api/http";
import { useAuth } from "../../auth/AuthContext";
import { AuthLayout, Field, FormError, onSubmit } from "./AuthLayout";

/** Where to go after login: the page that sent the user here, never another site. */
export function nextPath(params: URLSearchParams): string {
  const next = params.get("next") ?? "/";
  return next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [unverified, setUnverified] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError("");
    setUnverified(false);
    try {
      await login(email, password);
      navigate(nextPath(params), { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setUnverified(e instanceof ApiError && e.code === "unverified");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title="Đăng nhập">
      <form className="auth-form" onSubmit={onSubmit(submit)}>
        <Field
          label="Email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Field
          label="Mật khẩu"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <FormError error={error} />
        {unverified && (
          <p className="auth-note">
            Mở email xác nhận đã gửi cho bạn, hoặc{" "}
            <Link to={`/verify?resend=${encodeURIComponent(email)}`}>gửi lại email xác nhận</Link>.
          </p>
        )}
        <button className="btn btn-primary auth-submit" disabled={busy}>
          {busy ? "Đang đăng nhập…" : "Đăng nhập"}
        </button>
      </form>
      <div className="auth-links">
        <Link to="/forgot">Quên mật khẩu?</Link>
        <Link to="/signup">Tạo tài khoản</Link>
      </div>
    </AuthLayout>
  );
}
