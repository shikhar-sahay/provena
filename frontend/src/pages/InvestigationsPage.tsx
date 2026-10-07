// Investigation discovery: dense table with search, status filter, and
// client-side sorting over the investigations the user may see.

import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowDown, ArrowUp, ArrowUpDown, FolderKanban, Search } from "lucide-react";
import { api } from "../api/client";
import type { Investigation, InvestigationStatus } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PriorityBadge, StatusBadge } from "../components/Badge";
import { Button } from "../components/Button";
import { Input, Select } from "../components/Field";
import { NewInvestigationDialog } from "../components/NewInvestigationDialog";
import { EmptyState, ErrorState, PageHeader, TableSkeleton } from "../components/StateViews";
import { actionErrorMessage } from "../lib/errors";
import { displayName, timeAgo } from "../lib/format";

type SortKey = "updated" | "title" | "case" | "status" | "priority";
type SortDir = "asc" | "desc";

const STATUS_FILTERS: (InvestigationStatus | "")[] = [
  "",
  "open",
  "in_progress",
  "under_review",
  "closed",
  "archived",
];

const STATUS_LABEL: Record<string, string> = {
  "": "All statuses",
  open: "Open",
  in_progress: "In progress",
  under_review: "Under review",
  closed: "Closed",
  archived: "Archived",
};

const PRIORITY_RANK: Record<string, number> = { low: 0, medium: 1, high: 2, critical: 3 };

export default function InvestigationsPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [items, setItems] = useState<Investigation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState(params.get("q") ?? "");
  const [status, setStatus] = useState<InvestigationStatus | "">("");
  const [sortKey, setSortKey] = useState<SortKey>("updated");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const canCreate = user?.role === "admin" || user?.role === "investigator";

  useEffect(() => {
    let cancelled = false;
    api
      .listInvestigations()
      .then((data) => {
        if (cancelled) return;
        setItems(data);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(actionErrorMessage(err, "Could not load investigations."));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setParams(search.trim() ? { q: search.trim() } : {}, { replace: true });
  }, [search, setParams]);

  const visible = useMemo(() => {
    const term = search.trim().toLowerCase();
    const filtered = (items ?? []).filter((inv) => {
      if (status && inv.status !== status) return false;
      if (!term) return true;
      return (
        inv.title.toLowerCase().includes(term) ||
        inv.case_number.toLowerCase().includes(term) ||
        displayName(inv.lead_investigator).toLowerCase().includes(term)
      );
    });
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      switch (sortKey) {
        case "title":
          return a.title.localeCompare(b.title) * dir;
        case "case":
          return a.case_number.localeCompare(b.case_number) * dir;
        case "status":
          return a.status.localeCompare(b.status) * dir;
        case "priority":
          return (PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority]) * dir;
        case "updated":
        default:
          return a.updated_at.localeCompare(b.updated_at) * dir;
      }
    });
  }, [items, search, status, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "title" || key === "case" ? "asc" : "desc");
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Investigations"
        description="Cases you participate in. Admins see every investigation."
      />

      {items !== null && items.length > 0 && (
        <p aria-live="polite" className="text-[13px] text-ink3">
          {visible.length === items.length ? (
            <>
              <span className="font-semibold text-ink tabular-nums">{items.length}</span>{" "}
              {items.length === 1 ? "investigation" : "investigations"}
              {" · "}
              <span className="font-semibold text-ink tabular-nums">
                {items.filter((inv) => inv.status !== "closed" && inv.status !== "archived").length}
              </span>{" "}
              active
            </>
          ) : (
            <>
              Showing <span className="font-semibold text-ink tabular-nums">{visible.length}</span>{" "}
              of <span className="font-semibold text-ink tabular-nums">{items.length}</span>
            </>
          )}
        </p>
      )}

      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative min-w-0 flex-1 sm:max-w-xs">
          <Search
            size={14}
            className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-ink3"
          />
          <Input
            type="search"
            aria-label="Search investigations"
            placeholder="Search title, case number, lead…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
        <Select
          aria-label="Filter by status"
          value={status}
          onChange={(e) => setStatus(e.target.value as InvestigationStatus | "")}
          className="sm:w-44"
        >
          {STATUS_FILTERS.map((s) => (
            <option key={s || "all"} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </Select>
      </div>

      {error && <ErrorState body={error} onRetry={() => window.location.reload()} />}
      {items === null && !error && <TableSkeleton rows={6} />}

      {items !== null && items.length === 0 && (
        <EmptyState
          icon={<FolderKanban size={22} />}
          title="No investigations yet"
          body={
            canCreate
              ? "Create your first investigation to open a case with an assigned team."
              : "You are not assigned to any investigation yet. Ask an investigator to add you to a team."
          }
          action={
            canCreate ? (
              <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
                New investigation
              </Button>
            ) : undefined
          }
        />
      )}

      {items !== null && items.length > 0 && visible.length === 0 && (
        <EmptyState
          icon={<Search size={22} />}
          title="No matching investigations"
          body="Adjust the search term or status filter."
        />
      )}

      {visible.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-line">
          <table className="w-full min-w-[48rem] text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-surface text-[13px] text-ink2">
                <SortHeader label="Case" sortKey="case" current={sortKey} dir={sortDir} onSort={toggleSort} />
                <SortHeader label="Title" sortKey="title" current={sortKey} dir={sortDir} onSort={toggleSort} />
                <SortHeader label="Status" sortKey="status" current={sortKey} dir={sortDir} onSort={toggleSort} />
                <SortHeader label="Priority" sortKey="priority" current={sortKey} dir={sortDir} onSort={toggleSort} />
                <th className="px-3 py-2 font-medium">Lead</th>
                <SortHeader label="Updated" sortKey="updated" current={sortKey} dir={sortDir} onSort={toggleSort} />
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {visible.map((inv) => (
                <tr key={inv.id} className="pv-transition hover:bg-hover">
                  <td className="px-3 py-2.5 font-mono text-xs whitespace-nowrap text-ink2">
                    {inv.case_number}
                  </td>
                  <td className="max-w-xs px-3 py-2.5">
                    <Link
                      to={`/investigations/${inv.id}`}
                      className="block truncate font-medium text-ink hover:underline"
                    >
                      {inv.title}
                    </Link>
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <StatusBadge status={inv.status} />
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <PriorityBadge priority={inv.priority} />
                  </td>
                  <td className="max-w-40 truncate px-3 py-2.5 whitespace-nowrap text-ink2">
                    {displayName(inv.lead_investigator)}
                  </td>
                  <td className="px-3 py-2.5 text-[13px] whitespace-nowrap text-ink3">
                    {timeAgo(inv.updated_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <NewInvestigationDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function SortHeader({
  label,
  sortKey,
  current,
  dir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  dir: SortDir;
  onSort: (key: SortKey) => void;
}) {
  const active = current === sortKey;
  const Icon = !active ? ArrowUpDown : dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th className="px-3 py-2 font-medium">
      <button
        onClick={() => onSort(sortKey)}
        aria-label={`Sort by ${label.toLowerCase()}`}
        className="pv-transition inline-flex cursor-pointer items-center gap-1 hover:text-ink"
      >
        {label}
        <Icon size={12} className={active ? "text-ink" : "text-ink3"} />
      </button>
    </th>
  );
}
