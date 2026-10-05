// Login screen with Provena branding, validation, errors, and loading state.

import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { buttonPrimaryClass, inputClass, labelClass } from "../components/ui";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!identifier.trim() || !password) {
      setError("Enter your username or email and password.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await login(identifier.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 text-slate-100">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <p className="text-2xl font-semibold tracking-tight">Provena</p>
          <p className="mt-1 text-sm text-slate-400">Digital Investigation Management Platform</p>
        </div>

        <form
          onSubmit={(e) => void onSubmit(e)}
          className="rounded-lg border border-slate-800 bg-slate-900 p-6"
        >
          <h1 className="text-lg font-semibold">Log in</h1>
          <p className="mt-1 text-sm text-slate-400">
            Use your Provena account to access investigations.
          </p>

          <div className="mt-5 space-y-4">
            <div>
              <label htmlFor="identifier" className={labelClass}>
                Username or email
              </label>
              <input
                id="identifier"
                type="text"
                autoComplete="username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                className={inputClass}
                placeholder="investigator"
              />
            </div>
            <div>
              <label htmlFor="password" className={labelClass}>
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
                placeholder="Your password"
              />
            </div>
          </div>

          {error && (
            <p role="alert" className="mt-4 rounded-md bg-red-950 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          )}

          <button type="submit" disabled={busy} className={`${buttonPrimaryClass} mt-5 w-full`}>
            {busy ? "Logging in…" : "Log in"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-slate-500">
          Local development logins are documented in docs/development.md
        </p>
      </div>
    </div>
  );
}
