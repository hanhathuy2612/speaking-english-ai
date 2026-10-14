import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { api } from "../../api/http";
import type { User } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { AuthLayout, Field, FormError, onSubmit } from "./AuthLayout";

/** Pages reached by email: sign-up, confirming the address, and resetting a forgotten password
 * (docs/features/accounts.md). The server answers the same whether or not an email has an account. */

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/api/auth/signup", { body: { name, email, password } });
      setSent(true);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };

  if (sent)
    return (
      <AuthLayout title="Kiểm tra email">
        <p>
          Nếu <strong>{email}</strong> chưa có tài khoản, app vừa gửi tới đó một link xác nhận (hết hạn sau 48 giờ). Bấm
          link để kích hoạt tài khoản rồi đăng nhập.
        </p>
        <p className="auth-note">Không thấy email? Xem thư mục Spam, hoặc gửi lại ở trang đăng nhập.</p>
        <Link to={`/login?email=${encodeURIComponent(email)}`}>Về trang đăng nhập</Link>
      </AuthLayout>
    );

  return (
    <AuthLayout title="Tạo tài khoản">
      <form className="auth-form" onSubmit={onSubmit(submit)}>
        <Field label="Tên" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
        <Field
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Field
          label="Mật khẩu"
          type="password"
          autoComplete="new-password"
          hint="Ít nhất 8 ký tự."
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <FormError error={error} />
        <button className="btn btn-primary auth-submit" disabled={busy}>
          {busy ? "Đang gửi…" : "Tạo tài khoản"}
        </button>
      </form>
      <div className="auth-links">
        <span className="auth-note">Đã có tài khoản?</span>
        <Link to="/login">Đăng nhập</Link>
      </div>
    </AuthLayout>
  );
}

/** /verify?token=... from the email (logs in on success), or /verify?resend=email to send it again. */
export function VerifyPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [email, setEmail] = useState(params.get("resend") ?? "");
  const [sent, setSent] = useState(false);
  const tried = useRef(false);

  useEffect(() => {
    if (!token || tried.current) return; // StrictMode runs effects twice; a token works only once
    tried.current = true;
    api<User>("/api/auth/verify", { body: { token } })
      .then((u) => {
        setUser(u);
        navigate("/", { replace: true });
      })
      .catch((e) => setError(message(e)));
  }, [token, setUser, navigate]);

  const resend = async () => {
    setError("");
    try {
      await api("/api/auth/resend", { body: { email } });
      setSent(true);
    } catch (e) {
      setError(message(e));
    }
  };

  if (token && !error)
    return (
      <AuthLayout title="Xác nhận email">
        <p>Đang xác nhận…</p>
      </AuthLayout>
    );

  return (
    <AuthLayout title="Xác nhận email">
      <FormError error={error} />
      {sent ? (
        <p>Nếu {email} có tài khoản chưa xác nhận, app vừa gửi lại link xác nhận tới đó.</p>
      ) : (
        <form className="auth-form" onSubmit={onSubmit(resend)}>
          <p className="auth-note">Nhập email đã đăng ký để nhận link xác nhận mới.</p>
          <Field
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button className="btn btn-primary auth-submit">Gửi lại email xác nhận</button>
        </form>
      )}
      <Link to="/login">Về trang đăng nhập</Link>
    </AuthLayout>
  );
}

export function ForgotPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    try {
      await api("/api/auth/forgot", { body: { email } });
      setSent(true);
    } catch (e) {
      setError(message(e));
    }
  };

  return (
    <AuthLayout title="Quên mật khẩu">
      {sent ? (
        <p>Nếu {email} có tài khoản, app vừa gửi tới đó link đặt lại mật khẩu (hết hạn sau 1 giờ).</p>
      ) : (
        <form className="auth-form" onSubmit={onSubmit(submit)}>
          <Field
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <FormError error={error} />
          <button className="btn btn-primary auth-submit">Gửi link đặt lại mật khẩu</button>
        </form>
      )}
      <Link to="/login">Về trang đăng nhập</Link>
    </AuthLayout>
  );
}

export function ResetPage() {
  const [params] = useSearchParams();
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    if (password !== again) return setError("Hai lần nhập mật khẩu không giống nhau.");
    try {
      setUser(await api<User>("/api/auth/reset", { body: { token: params.get("token") ?? "", password } }));
      navigate("/", { replace: true });
    } catch (e) {
      setError(message(e));
    }
  };

  return (
    <AuthLayout title="Đặt mật khẩu mới">
      <form className="auth-form" onSubmit={onSubmit(submit)}>
        <Field
          label="Mật khẩu mới"
          type="password"
          autoComplete="new-password"
          hint="Ít nhất 8 ký tự."
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Field
          label="Nhập lại mật khẩu mới"
          type="password"
          autoComplete="new-password"
          required
          value={again}
          onChange={(e) => setAgain(e.target.value)}
        />
        <FormError error={error} />
        <button className="btn btn-primary auth-submit">Đặt mật khẩu</button>
      </form>
      <Link to="/forgot">Gửi lại link</Link>
    </AuthLayout>
  );
}
