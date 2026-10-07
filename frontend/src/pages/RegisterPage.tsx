import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { BrandLockup } from "../components/Brand";
import { Button } from "../components/Button";
import { Field, Input } from "../components/Field";
import { ThemeToggle } from "../components/ThemeToggle";
import { actionErrorMessage } from "../lib/errors";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register({ username: username.trim(), email: email.trim(), full_name: fullName.trim(), password });
      navigate("/onboarding", { replace: true });
    } catch (err) {
      setError(actionErrorMessage(err, "Could not create the account."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
      <div className="absolute top-4 right-4"><ThemeToggle /></div>
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center"><BrandLockup height={30} /></div>
        <form onSubmit={(event) => void submit(event)} className="space-y-4 rounded-lg border border-line bg-surface p-6 shadow-(--shadow)">
          <div><h1 className="text-base font-semibold">Create your account</h1><p className="mt-1 text-sm text-ink2">Next, create a workspace or join one with an invite code.</p></div>
          <Field label="Full name" htmlFor="register-name"><Input id="register-name" value={fullName} onChange={(e) => setFullName(e.target.value)} autoFocus /></Field>
          <Field label="Username" htmlFor="register-username"><Input id="register-username" value={username} onChange={(e) => setUsername(e.target.value)} minLength={3} required /></Field>
          <Field label="Email" htmlFor="register-email"><Input id="register-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
          <Field label="Password" htmlFor="register-password" hint="Use at least 8 characters."><Input id="register-password" type="password" autoComplete="new-password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required /></Field>
          {error && <p role="alert" className="rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-sm text-danger-ink">{error}</p>}
          <Button variant="primary" type="submit" loading={busy} className="w-full">Create account</Button>
          <p className="text-center text-sm text-ink3">Already have an account? <Link className="font-medium text-ink hover:underline" to="/login">Sign in</Link></p>
        </form>
      </div>
    </div>
  );
}
