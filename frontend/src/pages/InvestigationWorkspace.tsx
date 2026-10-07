// Investigation workspace: case header, section tabs, and shared context.
// Overview, Evidence, AI Analysis, Timeline, Custody, Reports, and Audit Log
// are functional. Findings is honestly marked as planned.

import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { ApiError, api } from "../api/client";
import type { Investigation } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Avatar } from "../components/Brand";
import { PriorityBadge, StatusBadge } from "../components/Badge";
import { EmptyState, ErrorState, Skeleton } from "../components/StateViews";
import { actionErrorMessage } from "../lib/errors";
import { displayName, timeAgo } from "../lib/format";

export interface WorkspaceContext {
  inv: Investigation;
  setInv: (inv: Investigation) => void;
  canManage: boolean;
  archivedLocked: boolean;
}

const TABS = [
  { to: "", label: "Overview", end: true },
  { to: "evidence", label: "Evidence", end: false },
  { to: "analysis", label: "AI Analysis", end: false },
  { to: "timeline", label: "Timeline", end: true },
  { to: "custody", label: "Custody", end: true },
  { to: "reports", label: "Reports", end: true },
  { to: "audit", label: "Audit Log", end: true },
];

const PLANNED_TABS = [
  { label: "Findings", note: "Investigator findings curation arrives in a later milestone." },
];

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
      else setError(actionErrorMessage(err, "Could not load the investigation."));
    }
  }, [id]);

  useEffect(() => {
    setInv(null);
    void load();
  }, [load]);

  if (notFound) {
    return (
      <EmptyState
        title="Investigation not found"
        body="It may not exist, or you may not have access to it. Non-members see this page instead of a permission error."
        action={<Link to="/investigations" className="text-sm font-medium text-accentink hover:underline">Back to investigations</Link>}
      />
    );
  }
  if (error) return <ErrorState body={error} onRetry={() => void load()} />;
  if (!inv || !user) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  const canManage =
    user.role === "admin" ||
    user.id === inv.created_by.id ||
    user.id === inv.lead_investigator.id;
  const archivedLocked = inv.status === "archived" && user.role !== "admin";

  return (
    <div>
      <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-[13px] text-ink3">
        <Link to="/investigations" className="hover:text-ink2 hover:underline">
          Investigations
        </Link>
        <ChevronRight size={13} aria-hidden="true" />
        <span className="font-mono" aria-current="page">
          {inv.case_number}
        </span>
      </nav>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 className="text-xl font-semibold tracking-tight">{inv.title}</h1>
        <StatusBadge status={inv.status} />
        <PriorityBadge priority={inv.priority} />
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-ink2">
        <span>
          Lead <span className="font-medium text-ink">{displayName(inv.lead_investigator)}</span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="flex -space-x-1.5">
            {inv.members.slice(0, 4).map((m) => (
              <span key={m.user.id} className="rounded-full ring-2 ring-canvas">
                <Avatar name={m.user.username} />
              </span>
            ))}
          </span>
          {inv.members.length} {inv.members.length === 1 ? "member" : "members"}
        </span>
        <span>Updated {timeAgo(inv.updated_at)}</span>
      </div>

      <div
        role="tablist"
        aria-label="Investigation sections"
        className="mt-4 flex gap-0.5 overflow-x-auto border-b border-line text-sm"
      >
        {TABS.map((tab) => (
          <NavLink
            key={tab.label}
            to={tab.to}
            end={tab.end}
            role="tab"
            className={({ isActive }) =>
              `pv-transition -mb-px shrink-0 border-b-2 px-3 py-2 font-medium whitespace-nowrap ${
                isActive
                  ? "border-ink text-ink"
                  : "border-transparent text-ink2 hover:border-linestrong hover:text-ink"
              }`
            }
          >
            {tab.label}
          </NavLink>
        ))}
        {PLANNED_TABS.map((tab) => (
          <span
            key={tab.label}
            role="tab"
            aria-disabled="true"
            title={tab.note}
            className="flex shrink-0 cursor-not-allowed items-center gap-1.5 border-b-2 border-transparent px-3 py-2 whitespace-nowrap text-ink3"
          >
            {tab.label}
            <span className="rounded border border-line px-1 py-px text-[10px] font-medium tracking-wide uppercase">
              Planned
            </span>
          </span>
        ))}
      </div>

      <div className="mt-5">
        <Outlet context={{ inv, setInv, canManage, archivedLocked } satisfies WorkspaceContext} />
      </div>
    </div>
  );
}
