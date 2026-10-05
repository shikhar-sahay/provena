// Evidence tab: filterable evidence list with registration action.

import { useCallback, useEffect, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { Evidence, EvidenceType, IntegrityStatus } from "../api/client";
import {
  EVIDENCE_TYPE_LABELS,
  IntegrityBadge,
  buttonPrimaryClass,
  formatBytes,
  formatDate,
  inputClass,
  labelClass,
} from "../components/ui";
import { ErrorBlock } from "./DashboardPage";
import type { WorkspaceContext } from "./InvestigationWorkspace";

const TYPE_OPTIONS: (EvidenceType | "")[] = [
  "",
  "log",
  "document",
  "image",
  "network",
  "email",
  "device",
  "archive",
  "other",
];
const INTEGRITY_OPTIONS: (IntegrityStatus | "")[] = [
  "",
  "not_verified",
  "verified",
  "mismatch",
  "unavailable",
];

export default function EvidenceTab() {
  const { id } = useParams<{ id: string }>();
  const { canManage, archivedLocked } = useOutletContext<WorkspaceContext>();
  const [items, setItems] = useState<Evidence[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<EvidenceType | "">("");
  const [integrityFilter, setIntegrityFilter] = useState<IntegrityStatus | "">("");
  const [query, setQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const invId = Number(id);

  const load = useCallback(async () => {
    try {
      const data = await api.listEvidence(invId, {
        evidence_type: typeFilter || undefined,
        integrity_status: integrityFilter || undefined,
        q: query || undefined,
      });
      setItems(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load evidence.");
    }
  }, [invId, typeFilter, integrityFilter, query]);

  useEffect(() => {
    setItems(null);
    void load();
  }, [load]);

  const canRegister = canManage && !archivedLocked;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Evidence</h2>
          <p className="text-sm text-slate-400">
            Registered files with SHA-256 baselines and custody tracking.
          </p>
        </div>
        {canRegister && (
          <Link to="register" className={buttonPrimaryClass}>
            Register evidence
          </Link>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(searchInput.trim());
        }}
        className="mt-4 grid gap-3 sm:grid-cols-4"
      >
        <div className="sm:col-span-2">
          <label htmlFor="evidence-search" className={labelClass}>
            Search
          </label>
          <input
            id="evidence-search"
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Title, number, or filename…"
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="evidence-type" className={labelClass}>
            Type
          </label>
          <select
            id="evidence-type"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as EvidenceType | "")}
            className={inputClass}
          >
            {TYPE_OPTIONS.map((t) => (
              <option key={t || "all"} value={t}>
                {t ? EVIDENCE_TYPE_LABELS[t] : "All types"}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="evidence-integrity" className={labelClass}>
            Integrity
          </label>
          <select
            id="evidence-integrity"
            value={integrityFilter}
            onChange={(e) => setIntegrityFilter(e.target.value as IntegrityStatus | "")}
            className={inputClass}
          >
            {INTEGRITY_OPTIONS.map((s) => (
              <option key={s || "all"} value={s}>
                {s ? s.replace(/_/g, " ") : "All states"}
              </option>
            ))}
          </select>
        </div>
      </form>

      {error && (
        <div className="mt-4">
          <ErrorBlock message={error} />
        </div>
      )}
      {items === null && !error && (
        <p className="mt-4 text-sm text-slate-400">Loading evidence…</p>
      )}
      {items !== null && items.length === 0 && (
        <div className="mt-4 rounded-lg border border-dashed border-slate-700 p-8 text-center">
          <p className="text-sm font-medium text-slate-300">No evidence registered</p>
          <p className="mt-1 text-sm text-slate-500">
            {canRegister
              ? "Register the first evidence item for this investigation."
              : "No evidence has been registered yet."}
          </p>
        </div>
      )}
      {items !== null && items.length > 0 && (
        <div className="mt-4 overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Item</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Integrity</th>
                <th className="px-4 py-3 font-medium">Holder</th>
                <th className="px-4 py-3 font-medium">Registered</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 bg-slate-900/40">
              {items.map((item) => (
                <tr key={item.id} className="hover:bg-slate-800/40">
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-300">
                    {item.evidence_number}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`${item.id}`}
                      className="font-medium text-sky-300 hover:text-sky-200"
                    >
                      {item.title}
                    </Link>
                    <p className="text-xs text-slate-500">
                      {item.original_filename} · {formatBytes(item.file_size)}
                    </p>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-300">
                    {EVIDENCE_TYPE_LABELS[item.evidence_type]}
                  </td>
                  <td className="px-4 py-3">
                    <IntegrityBadge status={item.integrity_status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-300">
                    {item.current_holder
                      ? item.current_holder.full_name || item.current_holder.username
                      : "Unknown"}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                    {formatDate(item.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
