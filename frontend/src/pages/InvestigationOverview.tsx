// Investigation overview: case details, settings dialog, and team management.

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useOutletContext } from "react-router-dom";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "../api/client";
import type { Investigation, InvestigationStatus, Priority, User } from "../api/client";
import { Avatar } from "../components/Brand";
import { Button } from "../components/Button";
import { ConfirmDialog, Dialog } from "../components/Dialog";
import { Field, Input, Select, Textarea } from "../components/Field";
import { RoleBadge, STATUS_LABELS } from "../components/Badge";
import { useToast } from "../components/Toast";
import { actionErrorMessage } from "../lib/errors";
import { displayName, formatDate } from "../lib/format";
import type { WorkspaceContext } from "./InvestigationWorkspace";

const STATUSES: InvestigationStatus[] = ["open", "in_progress", "under_review", "closed", "archived"];
const PRIORITIES: Priority[] = ["low", "medium", "high", "critical"];

export default function InvestigationOverview() {
  const { inv, setInv, canManage, archivedLocked } = useOutletContext<WorkspaceContext>();
  const [editing, setEditing] = useState(false);

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <section className="rounded-md border border-line bg-surface lg:col-span-2">
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <h2 className="text-sm font-semibold">Case details</h2>
          {canManage && !archivedLocked && (
            <Button variant="ghost" size="sm" icon={<Pencil size={13} />} onClick={() => setEditing(true)}>
              Edit
            </Button>
          )}
        </div>
        <div className="px-4 py-3">
          <p className="text-sm whitespace-pre-wrap">{inv.description || "No description provided."}</p>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3">
            <DetailItem label="Case number" mono value={inv.case_number} />
            <DetailItem label="Priority" value={inv.priority.charAt(0).toUpperCase() + inv.priority.slice(1)} />
            <DetailItem label="Created" value={formatDate(inv.created_at)} />
            <DetailItem label="Updated" value={formatDate(inv.updated_at)} />
            <DetailItem label="Closed" value={formatDate(inv.closed_at)} />
            <DetailItem
              label="Created by"
              value={`${displayName(inv.created_by)} (${inv.created_by.username})`}
            />
          </dl>
          {archivedLocked && (
            <p className="mt-4 rounded-md border border-line bg-hover px-3 py-2 text-[13px] text-ink2">
              This investigation is archived and read-only. Only admins can change it.
            </p>
          )}
        </div>
      </section>

      <TeamCard inv={inv} canManage={canManage && !archivedLocked} onChanged={setInv} />

      <EditDialog open={editing} onClose={() => setEditing(false)} inv={inv} onSaved={setInv} />
    </div>
  );
}

function DetailItem({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-ink3">{label}</dt>
      <dd className={`mt-0.5 truncate text-ink ${mono ? "font-mono text-[13px]" : ""}`}>{value}</dd>
    </div>
  );
}

function EditDialog({
  open,
  onClose,
  inv,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  inv: Investigation;
  onSaved: (v: Investigation) => void;
}) {
  const { notify } = useToast();
  const [title, setTitle] = useState(inv.title);
  const [description, setDescription] = useState(inv.description);
  const [priority, setPriority] = useState<Priority>(inv.priority);
  const [status, setStatus] = useState<InvestigationStatus>(inv.status);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTitle(inv.title);
    setDescription(inv.description);
    setPriority(inv.priority);
    setStatus(inv.status);
    setTitleError(null);
    setError(null);
  }, [open, inv]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setTitleError("A title is required.");
      return;
    }
    setTitleError(null);
    setError(null);
    setBusy(true);
    try {
      const updated = await api.updateInvestigation(inv.id, {
        title: title.trim(),
        description,
        priority,
        status,
      });
      onSaved(updated);
      notify("success", "Investigation updated.");
      onClose();
    } catch (err) {
      setError(actionErrorMessage(err, "Could not save changes."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Edit investigation"
      description={`${inv.case_number} settings and lifecycle status.`}
      wide
    >
      <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
        <Field label="Title" htmlFor="edit-title" error={titleError}>
          <Input id="edit-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={255} autoFocus />
        </Field>
        <Field label="Description" htmlFor="edit-description">
          <Textarea id="edit-description" value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Priority" htmlFor="edit-priority">
            <Select id="edit-priority" value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Status" htmlFor="edit-status">
            <Select id="edit-status" value={status} onChange={(e) => setStatus(e.target.value as InvestigationStatus)}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s]}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        {error && (
          <p role="alert" className="rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-sm text-danger-ink">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" type="button" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" loading={busy}>
            Save changes
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function TeamCard({
  inv,
  canManage,
  onChanged,
}: {
  inv: Investigation;
  canManage: boolean;
  onChanged: (v: Investigation) => void;
}) {
  const { notify } = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);

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

  async function add(userId: number) {
    setBusy(true);
    try {
      onChanged(await api.addMember(inv.id, userId));
      notify("success", "Team member added.");
      setAdding(false);
    } catch (err) {
      notify("error", actionErrorMessage(err, "Could not add the member."));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!removing) return;
    setBusy(true);
    try {
      onChanged(await api.removeMember(inv.id, removing.id));
      notify("success", "Team member removed.");
      setRemoving(null);
    } catch (err) {
      notify("error", actionErrorMessage(err, "Could not remove the member."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="overflow-hidden rounded-md border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h2 className="text-sm font-semibold">Team · {inv.members.length}</h2>
        {canManage && (
          <Button variant="ghost" size="sm" icon={<Plus size={13} />} onClick={() => setAdding(true)}>
            Add
          </Button>
        )}
      </div>
      <div className="px-3 py-2">
        <p className="px-1 py-1 text-[13px] text-ink2">
          Lead: <span className="font-medium text-ink">{displayName(inv.lead_investigator)}</span>
        </p>
        <ul className="divide-y divide-line">
          {inv.members.map((m) => (
            <li key={m.user.id} className="flex items-center gap-2.5 px-1 py-2">
              <Avatar name={m.user.username} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {displayName(m.user)}
                  {m.team_role === "lead" && (
                    <span className="ml-1.5 rounded border border-info-line bg-info-bg px-1 py-px text-[10px] font-semibold tracking-wide text-info-ink uppercase">
                      Lead
                    </span>
                  )}
                </p>
                <p className="truncate text-xs text-ink3">
                  <RoleBadge role={m.user.role} /> <span className="ml-1">{m.user.username}</span>
                </p>
              </div>
              {canManage && m.user.id !== inv.lead_investigator.id && (
                <RemoveButton label={`Remove ${displayName(m.user)}`} onClick={() => setRemoving(m.user)} />
              )}
            </li>
          ))}
        </ul>
      </div>

      <Dialog
        open={adding}
        onClose={() => setAdding(false)}
        title="Add team member"
        description="Members can view the investigation and its evidence."
      >
        {candidates.length === 0 ? (
          <p className="text-sm text-ink2">Every active user is already on this team.</p>
        ) : (
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {candidates.map((u) => (
              <li key={u.id}>
                <button
                  onClick={() => void add(u.id)}
                  disabled={busy}
                  className="pv-transition flex w-full cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-left hover:bg-hover disabled:opacity-50"
                >
                  <Avatar name={u.username} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{displayName(u)}</span>
                    <span className="block truncate text-xs text-ink3">{u.username}</span>
                  </span>
                  <RoleBadge role={u.role} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Dialog>

      <ConfirmDialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        onConfirm={() => void remove()}
        busy={busy}
        title="Remove team member"
        body={
          removing
            ? `${displayName(removing)} will lose access to this investigation and its evidence.`
            : ""
        }
        confirmLabel="Remove"
      />
    </section>
  );
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="pv-transition shrink-0 cursor-pointer rounded-md p-1.5 text-ink3 hover:bg-hover hover:text-danger-ink"
    >
      <Trash2 size={14} />
    </button>
  );
}
