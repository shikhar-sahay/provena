import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { BrandLockup } from "../components/Brand";
import { Button } from "../components/Button";
import { Field, Input } from "../components/Field";
import { actionErrorMessage } from "../lib/errors";

export default function OnboardingPage() {
  const { refresh, logout } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"create" | "join">("create");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "create") await api.createWorkspace(value.trim());
      else await api.joinWorkspace(value.trim());
      await refresh();
      navigate("/", { replace: true });
    } catch (err) {
      setError(actionErrorMessage(err, mode === "create" ? "Could not create the workspace." : "Could not join the workspace."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center"><BrandLockup height={30} /></div>
        <form onSubmit={(event) => void submit(event)} className="space-y-5 rounded-lg border border-line bg-surface p-6 shadow-(--shadow)">
          <div><h1 className="text-base font-semibold">Set up your workspace</h1><p className="mt-1 text-sm text-ink2">A workspace is the organization boundary for members, investigations, and search.</p></div>
          <div className="grid grid-cols-2 rounded-md border border-line p-1">
            <button type="button" onClick={() => { setMode("create"); setValue(""); }} className={`rounded px-3 py-1.5 text-sm ${mode === "create" ? "bg-hover font-medium" : "text-ink2"}`}>Create workspace</button>
            <button type="button" onClick={() => { setMode("join"); setValue(""); }} className={`rounded px-3 py-1.5 text-sm ${mode === "join" ? "bg-hover font-medium" : "text-ink2"}`}>Join with code</button>
          </div>
          <Field label={mode === "create" ? "Workspace name" : "Invite code"} htmlFor="workspace-value">
            <Input id="workspace-value" value={value} onChange={(e) => setValue(e.target.value)} placeholder={mode === "create" ? "Digital Investigations Lab" : "PRV-..."} autoFocus required />
          </Field>
          {error && <p role="alert" className="rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-sm text-danger-ink">{error}</p>}
          <Button variant="primary" type="submit" loading={busy} className="w-full">{mode === "create" ? "Create workspace" : "Join workspace"}</Button>
          <button type="button" onClick={() => void logout()} className="w-full text-sm text-ink3 hover:text-ink">Sign out</button>
        </form>
      </div>
    </div>
  );
}
