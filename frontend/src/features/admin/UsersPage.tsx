import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/http";
import type { Role, User } from "../../api/types";
import { useUser } from "../../auth/AuthContext";
import { AppBar } from "../../components/AppBar";
import { Chip } from "../../components/ui";
import { fmtDate } from "../../lib/format";
import { Field, FormError, onSubmit } from "../auth/AuthLayout";
import { AdminNav } from "./AdminNav";
import "../../styles/auth.css";

function NewUserForm({ onCreated }: { onCreated: () => void }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("user");
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    try {
      await api("/api/admin/users", { body: { email, name, password, role } });
      setEmail("");
      setName("");
      setPassword("");
      setRole("user");
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <form className="card admin-card" onSubmit={onSubmit(submit)}>
      <h2>Tạo tài khoản</h2>
      <p className="admin-hint">Tài khoản do quản trị viên tạo dùng được ngay, không cần xác nhận email.</p>
      <div className="admin-grid">
        <Field label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Field label="Tên" value={name} onChange={(e) => setName(e.target.value)} />
        <Field
          label="Mật khẩu"
          type="text"
          autoComplete="off"
          hint="Ít nhất 8 ký tự. Gửi cho người dùng, họ tự đổi ở trang Tài khoản."
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <label className="field">
          <span className="field-label">Vai trò</span>
          <select className="field-input" value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="user">Người học</option>
            <option value="admin">Quản trị viên</option>
          </select>
        </label>
      </div>
      <FormError error={error} />
      <div>
        <button className="btn btn-primary">Tạo tài khoản</button>
      </div>
    </form>
  );
}

function UserRow({ u, me, onChange }: { u: User; me: User; onChange: (msg: string) => void }) {
  const patch = async (body: Record<string, unknown>, done: string) => {
    try {
      await api(`/api/admin/users/${u.id}`, { method: "PATCH", body });
      onChange(done);
    } catch (e) {
      onChange(e instanceof Error ? e.message : String(e));
    }
  };
  const resetPassword = () => {
    const password = window.prompt(`Mật khẩu mới cho ${u.email} (ít nhất 8 ký tự):`);
    if (password) void patch({ password }, `Đã đặt mật khẩu mới cho ${u.email}.`);
  };
  const self = u.id === me.id;

  return (
    <tr className={u.disabled ? "muted" : ""}>
      <td>
        <div className="admin-user-name">{u.name}</div>
        <div className="admin-user-email">{u.email}</div>
      </td>
      <td>
        <select
          className="field-input admin-role"
          value={u.role}
          disabled={self}
          aria-label={`Vai trò của ${u.email}`}
          onChange={(e) => void patch({ role: e.target.value }, `Đã đổi vai trò của ${u.email}.`)}
        >
          <option value="user">Người học</option>
          <option value="admin">Quản trị viên</option>
        </select>
      </td>
      <td>
        {u.disabled ? (
          <Chip tone="warning">Đã khóa</Chip>
        ) : u.verified ? (
          <Chip tone="success">Hoạt động</Chip>
        ) : (
          <Chip tone="warning">Chưa xác nhận email</Chip>
        )}
      </td>
      <td className="num">{fmtDate(u.created_at, false)}</td>
      <td>
        <div className="admin-actions">
          {!u.verified && (
            <button className="btn btn-sm" onClick={() => void patch({ verified: true }, `Đã xác nhận ${u.email}.`)}>
              Xác nhận email
            </button>
          )}
          <button className="btn btn-sm" onClick={resetPassword}>
            Đặt mật khẩu
          </button>
          {!self && (
            <button
              className="btn btn-sm"
              onClick={() =>
                void patch({ disabled: !u.disabled }, u.disabled ? `Đã mở khóa ${u.email}.` : `Đã khóa ${u.email}.`)
              }
            >
              {u.disabled ? "Mở khóa" : "Khóa"}
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

export function UsersPage() {
  const me = useUser();
  const [users, setUsers] = useState<User[] | null>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(() => {
    api<User[]>("/api/admin/users")
      .then(setUsers)
      .catch((e) => setMessage(e.message));
  }, []);
  useEffect(load, [load]);

  return (
    <>
      <AppBar />
      <main className="admin">
        <h1>Quản trị</h1>
        <AdminNav />
        <NewUserForm
          onCreated={() => {
            setMessage("Đã tạo tài khoản.");
            load();
          }}
        />
        <section className="card table-card">
          <h2>Người dùng {users && `(${users.length})`}</h2>
          {message && (
            <p className="admin-message" role="status">
              {message}
            </p>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Người dùng</th>
                  <th>Vai trò</th>
                  <th>Trạng thái</th>
                  <th className="num">Tạo ngày</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users?.map((u) => (
                  <UserRow
                    key={u.id}
                    u={u}
                    me={me}
                    onChange={(msg) => {
                      setMessage(msg);
                      load();
                    }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </>
  );
}
