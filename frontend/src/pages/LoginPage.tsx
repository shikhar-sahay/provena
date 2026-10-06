// Provena sign-in: brand lockup, minimal form, precise error semantics.

import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { BrandLockup } from "../components/Brand";
import { Button } from "../components/Button";
import { Field, Input } from "../components/Field";
import { loginErrorMessage } from "../lib/errors";

export default function LoginPage() {
  const { login } = useAuth();
  const { notify } = useToast();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!identifier.trim() || !password) {
      setFieldError("Enter your username or email and your password.");
      return;
    }
    setFieldError(null);
    setError(null);
    setBusy(true);
    try {
      await login(identifier.trim(), password);
      notify("success", "Welcome back.");
      navigate("/", { replace: true });
    } catch (err) {
      setError(loginErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <BrandLockup height={30} />
          <p className="max-w-xs text-sm text-ink2">
            Digital investigation management with traceable evidence.
          </p>
        </div>

        <form
          onSubmit={(e) => void onSubmit(e)}
          noValidate
          className="pv-animate-rise rounded-lg border border-line bg-surface p-6 shadow-(--shadow)"
        >
          <h1 className="text-[15px] font-semibold tracking-tight">Sign in to Provena</h1>

          <div className="mt-4 space-y-4">
            <Field label="Username or email" htmlFor="login-id" error={fieldError}>
              <Input
                id="login-id"
                type="text"
                autoComplete="username"
                autoFocus
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="investigator"
              />
            </Field>
            <Field label="Password" htmlFor="login-password">
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Your password"
              />
            </Field>
          </div>

          {error && (
            <p
              role="alert"
              className="mt-4 rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-sm text-danger-ink"
            >
              {error}
            </p>
          )}

          <Button variant="primary" type="submit" loading={busy} className="mt-5 w-full">
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-4 text-center text-[13px] text-ink3">
          Local development accounts are listed in docs/development.md
        </p>
      </div>
    </div>
  );
}
