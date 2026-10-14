import type { FormEvent, ReactNode } from "react";
import { ChatIcon } from "../../components/Icons";
import "../../styles/auth.css";

/** Centered card used by the pages shown before login (and by the email link pages). */
export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="auth">
      <div className="auth-brand">
        <span className="brand-mark" aria-hidden>
          <ChatIcon />
        </span>
        <span>Phòng tập nói</span>
      </div>
      <section className="card auth-card">
        <h1>{title}</h1>
        {children}
      </section>
    </main>
  );
}

export function Field({
  label,
  hint,
  ...input
}: { label: string; hint?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <input className="field-input" {...input} />
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function FormError({ error }: { error: string }) {
  return error ? (
    <p className="form-error" role="alert">
      {error}
    </p>
  ) : null;
}

/** Calls `fn` on submit with the default navigation prevented. */
export const onSubmit = (fn: () => void) => (e: FormEvent) => {
  e.preventDefault();
  fn();
};
