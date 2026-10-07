// Provena sign-in: brand lockup, minimal form, precise error semantics.

import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Fingerprint, Link2, ShieldCheck } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { BrandLockup } from "../components/Brand";
import { Button } from "../components/Button";
import { Field, Input } from "../components/Field";
import { ProvenanceMotif } from "../components/ProvenanceMotif";
import { loginErrorMessage } from "../lib/errors";

const PILLARS = [
  {
    icon: <ShieldCheck size={14} />,
    title: "Integrity first",
    body: "Every file carries a SHA-256 baseline. Analysis runs on verified bytes only.",
  },
  {
    icon: <Link2 size={14} />,
    title: "End-to-end provenance",
    body: "Artifacts link to exact lines, rows, paths, and pages. Correlations cite contributors.",
  },
  {
    icon: <Fingerprint size={14} />,
    title: "Accountable investigation",
    body: "Rule proposals show their reasoning. Humans accept or reject; nothing self-validates.",
  },
];

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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-canvas px-4 py-10">
      <ProvenanceMotif className="pointer-events-none absolute inset-0 h-full w-full text-ink" />

      <div className="pv-animate-rise relative grid w-full max-w-4xl items-center gap-10 lg:grid-cols-[1.1fr_1fr]">
        <div className="hidden lg:block">
          <BrandLockup height={32} />
          <p className="mt-5 max-w-sm text-[15px] leading-relaxed text-ink2">
            Evidence integrity, provenance, and accountable investigation, in one
            traceable workspace.
          </p>
          <ul className="mt-8 space-y-5">
            {PILLARS.map((pillar) => (
              <li key={pillar.title} className="flex gap-3">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-line bg-surface text-ink2">
                  {pillar.icon}
                </span>
                <span>
                  <span className="block text-sm font-semibold">{pillar.title}</span>
                  <span className="mt-0.5 block max-w-xs text-[13px] leading-relaxed text-ink2">
                    {pillar.body}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <div className="mb-6 flex flex-col items-center gap-3 text-center lg:hidden">
            <BrandLockup height={30} />
            <p className="max-w-xs text-sm text-ink2">
              Evidence integrity, provenance, and accountable investigation.
            </p>
          </div>

          <form
            onSubmit={(e) => void onSubmit(e)}
            noValidate
            className="rounded-lg border border-line bg-surface p-6 shadow-(--shadow)"
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
    </div>
  );
}
