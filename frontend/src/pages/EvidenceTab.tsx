// Evidence tab: dense forensic table with search and filters, plus a
// registration drawer. Registration is also deep-linkable via the
// evidence/register route, which renders the same form.

import { useCallback, useEffect, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { FileUp, Search, Upload } from "lucide-react";
import { api } from "../api/client";
import type { Evidence, EvidenceType, IntegrityStatus } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { EVIDENCE_TYPE_LABELS, INTEGRITY_LABELS, IntegrityBadge } from "../components/Badge";
import { Button } from "../components/Button";
import { Drawer } from "../components/Dialog";
import { Input, Select } from "../components/Field";
import { EmptyState, ErrorState, TableSkeleton } from "../components/StateViews";
import { RegisterEvidenceForm } from "../components/RegisterEvidenceForm";
import { actionErrorMessage } from "../lib/errors";
import { displayName, formatBytes, timeAgo } from "../lib/format";
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

export default function EvidenceTab({ registerOpen = false }: { registerOpen?: boolean }) {
  const { id } = useParams<{ id: string }>();
  const { canManage, archivedLocked } = useOutletContext<WorkspaceContext>();
  const { user } = useAuth();
  const [items, setItems] = useState<Evidence[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<EvidenceType | "">("");
  const [integrityFilter, setIntegrityFilter] = useState<IntegrityStatus | "">("");
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [registering, setRegistering] = useState(registerOpen);

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
      setError(actionErrorMessage(err, "Could not load evidence."));
    }
  }, [invId, typeFilter, integrityFilter, query]);

  useEffect(() => {
    setItems(null);
    void load();
  }, [load]);

  const canRegister = (canManage || user?.role === "evidence_custodian") && !archivedLocked;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-ink2">
          Registered files with SHA-256 baselines and custody tracking.
          {items !== null && items.length > 0 && (
            <span className="ml-2 text-ink3">
              {items.length} {items.length === 1 ? "item" : "items"}
            </span>
          )}
        </p>
        {canRegister && (
          <Button variant="primary" size="sm" icon={<Upload size={14} />} onClick={() => setRegistering(true)}>
            Register evidence
          </Button>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(searchInput.trim());
        }}
        className="flex flex-col gap-2 sm:flex-row"
      >
        <div className="relative min-w-0 flex-1 sm:max-w-xs">
          <Search
            size={14}
            className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-ink3"
          />
          <Input
            type="search"
            aria-label="Search evidence"
            placeholder="Title, number, or filename…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-8"
          />
        </div>
        <Select
          aria-label="Filter by type"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as EvidenceType | "")}
          className="sm:w-36"
        >
          {TYPE_OPTIONS.map((t) => (
            <option key={t || "all"} value={t}>
              {t ? EVIDENCE_TYPE_LABELS[t] : "All types"}
            </option>
          ))}
        </Select>
        <Select
          aria-label="Filter by integrity"
          value={integrityFilter}
          onChange={(e) => setIntegrityFilter(e.target.value as IntegrityStatus | "")}
          className="sm:w-44"
        >
          {INTEGRITY_OPTIONS.map((s) => (
            <option key={s || "all"} value={s}>
              {s ? INTEGRITY_LABELS[s] : "All states"}
            </option>
          ))}
        </Select>
      </form>

      {error && <ErrorState body={error} onRetry={() => void load()} />}
      {items === null && !error && <TableSkeleton rows={5} />}

      {items !== null && items.length === 0 && (
        <EmptyState
          icon={<FileUp size={22} />}
          title="No evidence registered"
          body={
            canRegister
              ? "Upload the first file. Provena stores it under its control, records a SHA-256 baseline, and opens custody."
              : "No evidence has been registered for this investigation yet."
          }
          action={
            canRegister ? (
              <Button variant="primary" size="sm" onClick={() => setRegistering(true)}>
                Register evidence
              </Button>
            ) : undefined
          }
        />
      )}

      {items !== null && items.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-line">
          <table className="w-full min-w-[56rem] text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-surface text-[13px] text-ink2">
                <th className="px-3 py-2 font-medium">Item</th>
                <th className="px-3 py-2 font-medium">Title</th>
                <th className="px-3 py-2 font-medium">Type</th>
                <th className="px-3 py-2 font-medium">Integrity</th>
                <th className="px-3 py-2 font-medium">Holder</th>
                <th className="px-3 py-2 font-medium">Registered</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {items.map((item) => (
                <tr key={item.id} className="pv-transition hover:bg-hover">
                  <td className="px-3 py-2.5 font-mono text-xs whitespace-nowrap text-ink2">
                    {item.evidence_number}
                  </td>
                  <td className="max-w-xs px-3 py-2.5">
                    <Link
                      to={`${item.id}`}
                      className="block truncate font-medium text-ink hover:underline"
                    >
                      {item.title}
                    </Link>
                    <span className="block truncate text-xs text-ink3">
                      {item.original_filename} · {formatBytes(item.file_size)}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap text-ink2">
                    {EVIDENCE_TYPE_LABELS[item.evidence_type]}
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    <IntegrityBadge status={item.integrity_status} />
                  </td>
                  <td className="max-w-36 truncate px-3 py-2.5 whitespace-nowrap text-ink2">
                    {item.current_holder ? displayName(item.current_holder) : "Unknown"}
                  </td>
                  <td className="px-3 py-2.5 text-[13px] whitespace-nowrap text-ink3">
                    {timeAgo(item.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Drawer
        open={registering}
        onClose={() => setRegistering(false)}
        title="Register evidence"
        description="The file is stored under Provena control and a SHA-256 baseline is recorded."
      >
        <RegisterEvidenceForm
          invId={invId}
          onDone={() => {
            setRegistering(false);
            void load();
          }}
        />
      </Drawer>
    </div>
  );
}
