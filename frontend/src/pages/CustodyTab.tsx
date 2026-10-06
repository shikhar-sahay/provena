// Investigation custody tab: cross-evidence custody activity with links
// into each item's full chain.

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRightLeft } from "lucide-react";
import { api } from "../api/client";
import type { InvestigationCustodyRow } from "../api/client";
import { CUSTODY_ACTION_LABELS } from "../components/Badge";
import { EmptyState, ErrorState, Skeleton } from "../components/StateViews";
import { actionErrorMessage } from "../lib/errors";
import { formatDate } from "../lib/format";

export default function CustodyTab() {
  const { id } = useParams<{ id: string }>();
  const [rows, setRows] = useState<InvestigationCustodyRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .investigationCustody(Number(id))
      .then((data) => {
        if (!cancelled) {
          setRows(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(actionErrorMessage(err, "Could not load custody activity."));
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <ErrorState body={error} onRetry={() => window.location.reload()} />;

  return (
    <div className="max-w-3xl">
      <p className="text-sm text-ink2">
        Recent chain-of-custody events across this investigation. The full
        per-item history lives on each evidence page.
      </p>
      {!rows ? (
        <div className="mt-4 space-y-3">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      ) : rows.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            icon={<ArrowRightLeft size={22} />}
            title="No custody events yet"
            body="Custody events appear here once evidence is registered."
          />
        </div>
      ) : (
        <ol className="relative mt-4 space-y-4 border-l border-line">
          {rows.map((row) => (
            <li key={row.id} className="relative pl-5">
              <span
                aria-hidden="true"
                className="absolute top-1 -left-[5px] h-2.5 w-2.5 rounded-full border-2 border-surface bg-ink3"
              />
              <p className="text-sm">
                <span className="font-medium">
                  {CUSTODY_ACTION_LABELS[row.action as keyof typeof CUSTODY_ACTION_LABELS] ?? row.action}
                </span>
                <Link
                  to={`/investigations/${id}/evidence/${row.evidence_id}`}
                  className="ml-2 font-mono text-xs text-accentink hover:underline"
                >
                  {row.evidence_number}
                </Link>
              </p>
              <p className="mt-0.5 text-[13px] text-ink2">
                {row.from_user ?? "…"} → {row.to_user ?? "…"}
                {row.notes ? ` · ${row.notes}` : ""}
              </p>
              <p className="mt-0.5 text-xs text-ink3">
                {row.performed_by ?? "System"} · {formatDate(row.created_at)}
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
