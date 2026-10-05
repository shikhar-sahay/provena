// Dashboard: counts and recent investigations derived from backend data.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { Investigation } from "../api/client";
import { PriorityBadge, StatusBadge, formatDate } from "../components/ui";

export default function DashboardPage() {
  const [items, setItems] = useState<Investigation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .listInvestigations()
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Could not load dashboard.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <ErrorBlock message={error} />;
  }
  if (items === null) {
    return <p className="text-sm text-slate-400">Loading dashboard…</p>;
  }

  const open = items.filter((i) => i.status === "open").length;
  const active = items.filter((i) => i.status === "in_progress" || i.status === "under_review").length;
  const closed = items.filter((i) => i.status === "closed" || i.status === "archived").length;
  const recent = [...items]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 5);

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
      <p className="mt-1 text-sm text-slate-400">
        Your investigations at a glance. Evidence and AI analysis are planned for later.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <StatCard label="Total accessible" value={items.length} />
        <StatCard label="Open" value={open} />
        <StatCard label="In progress / review" value={active} />
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <StatCard label="Closed / archived" value={closed} />
      </div>

      <h2 className="mt-8 text-lg font-semibold">Recent investigations</h2>
      {recent.length === 0 ? (
        <div className="mt-3 rounded-lg border border-dashed border-slate-700 p-8 text-center">
          <p className="text-sm font-medium text-slate-300">No investigations yet</p>
          <p className="mt-1 text-sm text-slate-500">
            Create your first investigation to start tracking a case.
          </p>
          <Link
            to="/investigations/new"
            className="mt-4 inline-block rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
          >
            New investigation
          </Link>
        </div>
      ) : (
        <ul className="mt-3 divide-y divide-slate-800 rounded-lg border border-slate-800 bg-slate-900">
          {recent.map((inv) => (
            <li key={inv.id}>
              <Link to={`/investigations/${inv.id}`} className="block px-4 py-3 hover:bg-slate-800/50">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      <span className="mr-2 font-mono text-xs text-slate-500">{inv.case_number}</span>
                      {inv.title}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Updated {formatDate(inv.updated_at)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <PriorityBadge priority={inv.priority} />
                    <StatusBadge status={inv.status} />
                  </div>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <p className="text-3xl font-semibold">{value}</p>
      <p className="mt-1 text-sm text-slate-400">{label}</p>
    </div>
  );
}

export function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-900 bg-red-950/40 p-6">
      <p className="text-sm font-medium text-red-200">Something went wrong</p>
      <p className="mt-1 text-sm text-red-300/80">{message}</p>
    </div>
  );
}
