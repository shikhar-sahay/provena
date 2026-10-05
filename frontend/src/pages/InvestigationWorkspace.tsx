// Investigation workspace: header plus tab navigation for the product framework.
// Overview, Evidence, Timeline, Custody, and Audit Log are functional.
// Findings, AI Analysis, and Reports are visibly marked planned.

import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { Investigation } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PriorityBadge, StatusBadge } from "../components/ui";
import { ErrorBlock } from "./DashboardPage";

export interface WorkspaceContext {
  inv: Investigation;
  setInv: (inv: Investigation) => void;
  canManage: boolean;
  archivedLocked: boolean;
}

const TABS = [
  { to: "", label: "Overview", end: true },
  { to: "evidence", label: "Evidence", end: false },
  { to: "timeline", label: "Timeline", end: true },
  { to: "custody", label: "Custody", end: true },
  { to: "audit", label: "Audit Log", end: true },
];

const PLANNED_TABS = ["Findings", "AI Analysis", "Reports"];

export default function InvestigationWorkspace() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [inv, setInv] = useState<Investigation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const detail = await api.getInvestigation(Number(id));
      setInv(detail);
      setError(null);
      setNotFound(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setNotFound(true);
      else setError(err instanceof ApiError ? err.message : "Could not load the investigation.");
    }
  }, [id]);

  useEffect(() => {
    setInv(null);
    void load();
  }, [load]);

  if (notFound) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-8 text-center">
        <p className="font-medium">Investigation not found</p>
        <p className="mt-1 text-sm text-slate-500">
          It may not exist, or you may not have access to it.
        </p>
      </div>
    );
  }
  if (error) return <ErrorBlock message={error} />;
  if (!inv || !user) return <p className="text-sm text-slate-400">Loading investigation…</p>;

  const canManage =
    user.role === "admin" ||
    user.id === inv.created_by.id ||
    user.id === inv.lead_investigator.id;
  const archivedLocked = inv.status === "archived" && user.role !== "admin";

  return (
    <div>
      <p className="font-mono text-xs text-slate-500">{inv.case_number}</p>
      <div className="mt-1 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{inv.title}</h1>
        <StatusBadge status={inv.status} />
        <PriorityBadge priority={inv.priority} />
      </div>

      <div className="mt-4 flex flex-wrap gap-1 border-b border-slate-800 text-sm">
        {TABS.map((tab) => (
          <NavLink
            key={tab.label}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              `px-3 py-2 ${
                isActive
                  ? "border-b-2 border-sky-500 font-medium text-sky-300"
                  : "text-slate-400 hover:text-slate-200"
              }`
            }
          >
            {tab.label}
          </NavLink>
        ))}
        {PLANNED_TABS.map((label) => (
          <span
            key={label}
            title="Planned, not implemented yet"
            className="cursor-not-allowed px-3 py-2 text-slate-600"
          >
            {label}
          </span>
        ))}
      </div>

      <div className="mt-6">
        <Outlet context={{ inv, setInv, canManage, archivedLocked } satisfies WorkspaceContext} />
      </div>
    </div>
  );
}
