// Investigations list with create action, loading/empty/error states.

import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { Investigation } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PriorityBadge, StatusBadge, buttonPrimaryClass, formatDate } from "../components/ui";
import { ErrorBlock } from "./DashboardPage";

export default function InvestigationsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<Investigation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canCreate = user?.role === "admin" || user?.role === "investigator";

  useEffect(() => {
    let cancelled = false;
    api
      .listInvestigations()
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Could not load investigations.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Investigations</h1>
          <p className="mt-1 text-sm text-slate-400">
            Investigations you participate in. Admins see all investigations.
          </p>
        </div>
        {canCreate && (
          <Link to="/investigations/new" className={buttonPrimaryClass}>
            New investigation
          </Link>
        )}
      </div>

      {error && (
        <div className="mt-6">
          <ErrorBlock message={error} />
        </div>
      )}
      {items === null && !error && (
        <p className="mt-6 text-sm text-slate-400">Loading investigations…</p>
      )}
      {items !== null && items.length === 0 && (
        <div className="mt-6 rounded-lg border border-dashed border-slate-700 p-8 text-center">
          <p className="text-sm font-medium text-slate-300">No investigations found</p>
          <p className="mt-1 text-sm text-slate-500">
            {canCreate
              ? "Create one to get started."
              : "You are not assigned to any investigation yet."}
          </p>
        </div>
      )}
      {items !== null && items.length > 0 && (
        <div className="mt-6 overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">Case</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Priority</th>
                <th className="px-4 py-3 font-medium">Lead</th>
                <th className="px-4 py-3 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 bg-slate-900/40">
              {items.map((inv) => (
                <tr key={inv.id} className="hover:bg-slate-800/40">
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-400">
                    {inv.case_number}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/investigations/${inv.id}`}
                      className="font-medium text-sky-300 hover:text-sky-200"
                    >
                      {inv.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={inv.status} />
                  </td>
                  <td className="px-4 py-3">
                    <PriorityBadge priority={inv.priority} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-300">
                    {inv.lead_investigator.full_name || inv.lead_investigator.username}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-500">
                    {formatDate(inv.updated_at)}
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
