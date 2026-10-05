import { useEffect, useState } from "react";

type Health = {
  status: string;
  app: string;
  env: string;
  db: string;
};

type BackendState =
  | { kind: "checking" }
  | { kind: "online"; health: Health }
  | { kind: "offline" };

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export default function App() {
  const [backend, setBackend] = useState<BackendState>({ kind: "checking" });

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/health`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error("bad status"))))
      .then((health: Health) => {
        if (!cancelled) setBackend({ kind: "online", health });
      })
      .catch(() => {
        if (!cancelled) setBackend({ kind: "offline" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <span className="text-lg font-semibold tracking-tight">Provena</span>
          <BackendBadge state={backend} />
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-16">
        <p className="text-sm font-medium uppercase tracking-widest text-sky-400">
          Development foundation
        </p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight">
          Digital Investigation Management Platform
        </h1>
        <p className="mt-4 max-w-2xl text-slate-400">
          Provena will centralize the lifecycle of a digital investigation — cases,
          evidence, chain of custody, and explainable AI-assisted analysis with
          human oversight. This shell only verifies the frontend and backend are
          wired up; the investigation workflow is planned, not yet implemented.
        </p>

        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          <FeatureCard
            title="Cases"
            body="Investigation lifecycle management. Planned."
          />
          <FeatureCard
            title="Evidence"
            body="Registration, SHA-256 integrity, custody. Planned."
          />
          <FeatureCard
            title="Analysis"
            body="Explainable correlation and reasoning. Planned."
          />
        </div>
      </main>
    </div>
  );
}

function BackendBadge({ state }: { state: BackendState }) {
  if (state.kind === "checking") {
    return (
      <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
        Checking backend…
      </span>
    );
  }
  if (state.kind === "offline") {
    return (
      <span className="rounded-full bg-red-950 px-3 py-1 text-xs text-red-300">
        Backend offline
      </span>
    );
  }
  return (
    <span className="rounded-full bg-emerald-950 px-3 py-1 text-xs text-emerald-300">
      Backend online · {state.health.env} · db: {state.health.db}
    </span>
  );
}

function FeatureCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-slate-400">{body}</p>
    </div>
  );
}
