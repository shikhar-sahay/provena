// Provena sign-in: brand lockup, minimal form, precise error semantics.

import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileKey2, GitFork, ScanSearch } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { BrandLockup } from "../components/Brand";
import { Button } from "../components/Button";
import { Field, Input } from "../components/Field";
import { ProvenanceMotif } from "../components/ProvenanceMotif";
import { ThemeToggle } from "../components/ThemeToggle";
import { loginErrorMessage } from "../lib/errors";

const PILLARS = [
  {
    icon: <FileKey2 size={18} strokeWidth={1.6} />,
    title: "Integrity first",
    body: "Every file carries a SHA-256 baseline. Analysis runs on verified bytes only.",
  },
  {
    icon: <GitFork size={18} strokeWidth={1.6} />,
    title: "End-to-end provenance",
    body: "Artifacts link to exact lines, rows, paths, and pages. Correlations cite contributors.",
  },
  {
    icon: <ScanSearch size={18} strokeWidth={1.6} />,
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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-canvas px-5 py-12 sm:px-8">
      <div className="absolute top-4 right-4 z-20">
        <ThemeToggle />
      </div>

      <ProvenanceMotif className="pv-motif pointer-events-none absolute -inset-[3%] h-[106%] w-[106%] text-ink" />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_63%_48%,transparent_0,var(--canvas)_72%)] opacity-35" />

      <div className="pv-animate-rise relative grid w-full max-w-5xl items-center gap-14 lg:grid-cols-[1.15fr_0.95fr] xl:gap-20">
        <div className="hidden lg:flex lg:flex-col lg:justify-center">
          <div className="max-w-lg space-y-10">
            <div className="space-y-4">
              <BrandLockup height={34} />
              <p className="max-w-md text-[17px] leading-relaxed text-ink2">
                Evidence integrity, provenance, and accountable investigation, in one
                traceable workspace.
              </p>
            </div>

            <ul className="space-y-6">
              {PILLARS.map((pillar) => (
                <li key={pillar.title} className="group flex items-start gap-4">
                  <span className="pv-transition mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-line bg-surface/80 text-ink2 shadow-sm group-hover:-translate-y-0.5 group-hover:border-linestrong group-hover:text-ink">
                    {pillar.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <span className="block text-[15px] font-semibold text-ink">{pillar.title}</span>
                    <span className="mt-1 block text-sm leading-relaxed text-ink2">
                      {pillar.body}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
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
            className="rounded-xl border border-line bg-surface/95 p-7 shadow-(--shadow) backdrop-blur-sm sm:p-8"
          >
            <p className="text-[11px] font-semibold tracking-[0.16em] text-ink3 uppercase">Secure case workspace</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">Welcome back</h1>
            <p className="mt-1 text-sm text-ink2">Sign in to continue to Provena.</p>

            <div className="mt-6 space-y-5">
              <Field label="Username or email" htmlFor="login-id" error={fieldError}>
                <Input
                  id="login-id"
                  type="text"
                  autoComplete="username"
                  autoFocus
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="Enter your username"
                  className="h-10 px-3"
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
                  className="h-10 px-3"
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

            <Button variant="primary" type="submit" loading={busy} className="mt-6 h-10 w-full shadow-sm hover:-translate-y-px">
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <p className="mt-4 text-center text-[13px] text-ink3">
            New to Provena? <Link to="/register" className="font-medium text-ink hover:underline">Create an account</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
