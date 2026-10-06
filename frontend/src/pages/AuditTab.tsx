// Investigation audit log: dense, inspectable accountability view with action
// filtering and expandable metadata. The log records that actions happened;
// chain of custody lives with the evidence.

import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { ChevronDown, ScrollText } from "lucide-react";
import { api } from "../api/client";
import type { AuditEntry } from "../api/client";
import { Select } from "../components/Field";
import { EmptyState, ErrorState, Skeleton } from "../components/StateViews";
import { actionLabel } from "../lib/activity";
import { actionErrorMessage } from "../lib/errors";
import { formatDate } from "../lib/format";

export default function AuditTab() {
  const { id } = useParams<{ id: string }>();
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .investigationAudit(Number(id))
      .then((data) => {
        if (!cancelled) {
          setEntries(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(actionErrorMessage(err, "Could not load the audit log."));
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const actions = useMemo(
    () => Array.from(new Set((entries ?? []).map((e) => e.action))).sort(),
    [entries],
  );
  const visible = useMemo(
    () => (entries ?? []).filter((e) => !filter || e.action === filter),
    [entries, filter],
  );

  if (error) return <ErrorState body={error} onRetry={() => window.location.reload()} />;

  return (
    <div className="max-w-3xl">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-ink2">
          Application actions on this investigation, recorded automatically.
        </p>
        {actions.length > 1 && (
          <Select
            aria-label="Filter by event type"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-52"
          >
            <option value="">All event types</option>
            {actions.map((a) => (
              <option key={a} value={a}>
                {actionLabel(a)}
              </option>
            ))}
          </Select>
        )}
      </div>

      {!entries ? (
        <div className="mt-4 space-y-3">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : visible.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            icon={<ScrollText size={22} />}
            title={entries.length === 0 ? "No audit events yet" : "No matching events"}
            body={
              entries.length === 0
                ? "Actions on this investigation will be recorded here."
                : "Adjust the event-type filter."
            }
          />
        </div>
      ) : (
        <ol className="mt-4 divide-y divide-line overflow-hidden rounded-md border border-line bg-surface">
          {visible.map((entry) => {
            const isOpen = expanded === entry.id;
            const meta = entry.event_metadata ?? {};
            const metaKeys = Object.keys(meta);
            const evidenceHint =
              typeof meta["evidence_number"] === "string" ? (meta["evidence_number"] as string) : null;
            return (
              <li key={entry.id}>
                <button
                  onClick={() => setExpanded(isOpen ? null : entry.id)}
                  aria-expanded={isOpen}
                  className="pv-transition flex w-full cursor-pointer items-center gap-3 px-4 py-2.5 text-left hover:bg-hover"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{actionLabel(entry.action)}</span>
                    <span className="block truncate text-xs text-ink3">
                      {entry.actor_username ?? "System"} · {formatDate(entry.created_at)}
                    </span>
                  </span>
                  {evidenceHint && (
                    <span className="shrink-0 font-mono text-xs text-ink3">{evidenceHint}</span>
                  )}
                  <ChevronDown
                    size={14}
                    aria-hidden="true"
                    className={`shrink-0 text-ink3 transition-transform ${isOpen ? "rotate-180" : ""}`}
                  />
                </button>
                {isOpen && metaKeys.length > 0 && (
                  <dl className="grid gap-x-6 gap-y-1 border-t border-line bg-canvas px-4 py-2.5 text-[13px] sm:grid-cols-2">
                    {metaKeys.map((key) => (
                      <div key={key} className="flex min-w-0 gap-2">
                        <dt className="shrink-0 text-ink3">{prettifyKey(key)}</dt>
                        <dd className="truncate font-mono text-xs text-ink2" title={String(meta[key])}>
                          {String(meta[key])}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

function prettifyKey(key: string): string {
  return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
