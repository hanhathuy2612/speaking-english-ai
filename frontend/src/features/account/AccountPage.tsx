import { useState } from "react";
import { useNavigate } from "react-router";
import { api, type LoginAnswer } from "../../api/http";
import { useAuth, useUser } from "../../auth/AuthContext";
import { AppBar } from "../../components/AppBar";
import { Chip } from "../../components/ui";
import { fmtDate } from "../../lib/format";
import { Field, FormError, onSubmit } from "../auth/AuthLayout";
import "../../styles/auth.css";

function PasswordForm() {
  const { loggedIn } = useAuth();
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const submit = async () => {
    setError("");
    setDone(false);
    if (password !== again) return setError("Hai lần nhập mật khẩu mới không giống nhau.");
    try {
      // New tokens: the old refresh token stops working with the old password.
      loggedIn(await api<LoginAnswer>("/api/auth/password", { body: { current, password } }));
      setDone(true);
      setCurrent("");
      setPassword("");
      setAgain("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <form className="card account-card auth-form" onSubmit={onSubmit(submit)}>
      <h2>Đổi mật khẩu</h2>
      <Field
        label="Mật khẩu hiện tại"
        type="password"
        autoComplete="current-password"
        required
        value={current}
        onChange={(e) => setCurrent(e.target.value)}
      />
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
      {done && <p className="form-ok">Đã đổi mật khẩu. Các thiết bị khác cần đăng nhập lại.</p>}
      <div>
        <button className="btn btn-primary">Đổi mật khẩu</button>
      </div>
    </form>
  );
}

export function AccountPage() {
  const user = useUser();
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <>
      <AppBar />
      <main className="account">
        <h1>Tài khoản</h1>
        <section className="card account-card">
          <dl className="account-info">
            <dt>Tên</dt>
            <dd>{user.name}</dd>
            <dt>Email</dt>
            <dd>{user.email}</dd>
            <dt>Vai trò</dt>
            <dd>
              <Chip tone={user.role === "admin" ? "success" : ""}>
                {user.role === "admin" ? "Quản trị viên" : "Người học"}
              </Chip>
            </dd>
            <dt>Tạo lúc</dt>
            <dd>{fmtDate(user.created_at)}</dd>
          </dl>
          <div>
            <button
              className="btn"
              onClick={async () => {
                await logout();
                navigate("/login", { replace: true });
              }}
            >
              Đăng xuất
            </button>
          </div>
        </section>
        <PasswordForm />
      </main>
    </>
  );
}
