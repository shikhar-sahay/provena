// Investigation custody tab: recent custody activity across all evidence.

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { InvestigationCustodyRow } from "../api/client";
import { CUSTODY_ACTION_LABELS, formatDate } from "../components/ui";
import { ErrorBlock } from "./DashboardPage";

export default function CustodyTab() {
  const { id } = useParams<{ id: string }>();
  const [rows, setRows] = useState<InvestigationCustodyRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .investigationCustody(Number(id))
      .then((data) => {
        if (!cancelled) setRows(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Could not load custody activity.");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <ErrorBlock message={error} />;

  return (
    <div>
      <h2 className="text-lg font-semibold">Custody activity</h2>
      <p className="mt-1 text-sm text-slate-400">
        Recent chain-of-custody events across this investigation. Full per-item
        history lives on each evidence page.
      </p>
      {!rows ? (
        <p className="mt-4 text-sm text-slate-400">Loading custody activity…</p>
      ) : rows.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-slate-700 p-8 text-center">
          <p className="text-sm font-medium text-slate-300">No custody events yet</p>
          <p className="mt-1 text-sm text-slate-500">
            Custody events appear here once evidence is registered.
          </p>
        </div>
      ) : (
        <ol className="mt-4 space-y-3">
          {rows.map((row) => (
            <li
              key={row.id}
              className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={`/investigations/${id}/evidence/${row.evidence_id}`}
                  className="font-mono text-xs text-sky-300 hover:text-sky-200"
                >
                  {row.evidence_number}
                </Link>
                <span className="font-medium text-slate-200">
                  {CUSTODY_ACTION_LABELS[row.action as keyof typeof CUSTODY_ACTION_LABELS] ?? row.action}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-400">
                {row.from_user ?? "…"} → {row.to_user ?? "…"}
                {row.notes ? ` · ${row.notes}` : ""}
              </p>
              <p className="text-xs text-slate-500">
                {row.performed_by ?? "System"} · {formatDate(row.created_at)}
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
