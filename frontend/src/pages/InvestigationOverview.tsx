// Investigation overview tab: details, permitted editing, and team management.

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useOutletContext } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { Investigation, InvestigationStatus, Priority, User } from "../api/client";
import {
  PriorityBadge,
  ROLE_LABELS,
  STATUS_LABELS,
  StatusBadge,
  buttonPrimaryClass,
  buttonSecondaryClass,
  formatDate,
  inputClass,
  labelClass,
} from "../components/ui";
import type { WorkspaceContext } from "./InvestigationWorkspace";

const STATUSES: InvestigationStatus[] = ["open", "in_progress", "under_review", "closed", "archived"];
const PRIORITIES: Priority[] = ["low", "medium", "high", "critical"];

export default function InvestigationOverview() {
  const { inv, setInv, canManage, archivedLocked } = useOutletContext<WorkspaceContext>();

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge status={inv.status} />
        <PriorityBadge priority={inv.priority} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Details</h2>
            <p className="mt-3 whitespace-pre-wrap text-sm text-slate-200">
              {inv.description || "No description provided."}
            </p>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <DetailItem label="Created" value={formatDate(inv.created_at)} />
              <DetailItem label="Updated" value={formatDate(inv.updated_at)} />
              <DetailItem label="Closed" value={formatDate(inv.closed_at)} />
              <DetailItem
                label="Created by"
                value={`${inv.created_by.full_name || inv.created_by.username} (${inv.created_by.username})`}
              />
            </dl>
          </section>

          {canManage && !archivedLocked ? (
            <EditSection inv={inv} onSaved={setInv} />
          ) : (
            archivedLocked && (
              <p className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-500">
                This investigation is archived and read-only. Only admins can change it.
              </p>
            )
          )}
        </div>

        <div>
          <TeamSection inv={inv} canManage={canManage && !archivedLocked} onChanged={setInv} />
        </div>
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-slate-200">{value}</dd>
    </div>
  );
}

function EditSection({ inv, onSaved }: { inv: Investigation; onSaved: (v: Investigation) => void }) {
  const [title, setTitle] = useState(inv.title);
  const [description, setDescription] = useState(inv.description);
  const [priority, setPriority] = useState<Priority>(inv.priority);
  const [status, setStatus] = useState<InvestigationStatus>(inv.status);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setError("A title is required.");
      return;
    }
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      const updated = await api.updateInvestigation(inv.id, {
        title: title.trim(),
        description,
        priority,
        status,
      });
      onSaved(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save changes.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
        Edit investigation
      </h2>
      <form onSubmit={(e) => void onSubmit(e)} className="mt-3 space-y-4">
        <div>
          <label htmlFor="edit-title" className={labelClass}>
            Title
          </label>
          <input
            id="edit-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputClass}
            maxLength={255}
          />
        </div>
        <div>
          <label htmlFor="edit-description" className={labelClass}>
            Description
          </label>
          <textarea
            id="edit-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={`${inputClass} min-h-24`}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="edit-priority" className={labelClass}>
              Priority
            </label>
            <select
              id="edit-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value as Priority)}
              className={inputClass}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="edit-status" className={labelClass}>
              Status
            </label>
            <select
              id="edit-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as InvestigationStatus)}
              className={inputClass}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </select>
          </div>
        </div>
        {error && (
          <p role="alert" className="rounded-md bg-red-950 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}
        {saved && <p className="text-sm text-emerald-300">Changes saved.</p>}
        <button type="submit" disabled={busy} className={buttonPrimaryClass}>
          {busy ? "Saving…" : "Save changes"}
        </button>
      </form>
    </section>
  );
}

function TeamSection({
  inv,
  canManage,
  onChanged,
}: {
  inv: Investigation;
  canManage: boolean;
  onChanged: (v: Investigation) => void;
}) {
  const [users, setUsers] = useState<User[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canManage) return;
    let cancelled = false;
    api
      .listUsers()
      .then((data) => {
        if (!cancelled) setUsers(data);
      })
      .catch(() => {
        if (!cancelled) setUsers([]);
      });
    return () => {
      cancelled = true;
    };
  }, [canManage]);

  const memberIds = new Set(inv.members.map((m) => m.user.id));
  const candidates = users.filter((u) => !memberIds.has(u.id));

  async function add() {
    if (!selected) return;
    setError(null);
    try {
      onChanged(await api.addMember(inv.id, Number(selected)));
      setSelected("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add member.");
    }
  }

  async function remove(userId: number) {
    setError(null);
    try {
      onChanged(await api.removeMember(inv.id, userId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove member.");
    }
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Team</h2>
      <p className="mt-2 text-sm">
        <span className="text-slate-500">Lead: </span>
        <span className="font-medium">
          {inv.lead_investigator.full_name || inv.lead_investigator.username}
        </span>
      </p>
      <ul className="mt-3 space-y-2">
        {inv.members.map((m) => (
          <li
            key={m.user.id}
            className="flex items-center justify-between gap-2 rounded-md bg-slate-800/60 px-3 py-2 text-sm"
          >
            <div className="min-w-0">
              <p className="truncate font-medium">
                {m.user.full_name || m.user.username}
                {m.team_role === "lead" && (
                  <span className="ml-2 rounded bg-sky-950 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-sky-300">
                    Lead
                  </span>
                )}
              </p>
              <p className="truncate text-xs text-slate-500">
                {ROLE_LABELS[m.user.role]} · {m.user.username}
              </p>
            </div>
            {canManage && m.user.id !== inv.lead_investigator.id && (
              <button
                onClick={() => void remove(m.user.id)}
                className="shrink-0 rounded border border-slate-700 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700"
              >
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>

      {canManage && (
        <div className="mt-4">
          <label htmlFor="add-member" className={labelClass}>
            Add member
          </label>
          <div className="flex gap-2">
            <select
              id="add-member"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className={inputClass}
            >
              <option value="">Select a user…</option>
              {candidates.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name || u.username} ({ROLE_LABELS[u.role]})
                </option>
              ))}
            </select>
            <button onClick={() => void add()} disabled={!selected} className={buttonSecondaryClass}>
              Add
            </button>
          </div>
          {error && <p className="mt-2 text-sm text-red-300">{error}</p>}
        </div>
      )}
    </section>
  );
}
