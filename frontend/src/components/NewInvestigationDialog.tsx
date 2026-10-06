// Investigation creation dialog, shared by the shell, dashboard, and list.

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Priority, User } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { actionErrorMessage } from "../lib/errors";
import { useToast } from "./Toast";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { Field, Input, Select, Textarea } from "./Field";

const PRIORITIES: Priority[] = ["low", "medium", "high", "critical"];

export function NewInvestigationDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { user } = useAuth();
  const { notify } = useToast();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [leadId, setLeadId] = useState("");
  const [users, setUsers] = useState<User[]>([]);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTitle("");
    setDescription("");
    setPriority("medium");
    setLeadId("");
    setTitleError(null);
    setError(null);
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
  }, [open ]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setTitleError("Give the investigation a title.");
      return;
    }
    setTitleError(null);
    setError(null);
    setBusy(true);
    try {
      const created = await api.createInvestigation({
        title: title.trim(),
        description: description.trim(),
        priority,
        lead_investigator_id: leadId ? Number(leadId) : undefined,
      });
      notify("success", `Investigation ${created.case_number} created.`);
      onClose();
      navigate(`/investigations/${created.id}`);
    } catch (err) {
      setError(actionErrorMessage(err, "Could not create the investigation."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New investigation"
      description="A case number is assigned automatically on creation."
      wide
    >
      <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
        <Field label="Title" htmlFor="new-inv-title" error={titleError}>
          <Input
            id="new-inv-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Suspected data exfiltration"
            maxLength={255}
            autoFocus
          />
        </Field>
        <Field label="Description" htmlFor="new-inv-description">
          <Textarea
            id="new-inv-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Background, scope, and initial observations."
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Priority" htmlFor="new-inv-priority">
            <Select
              id="new-inv-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value as Priority)}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Lead investigator" htmlFor="new-inv-lead">
            <Select id="new-inv-lead" value={leadId} onChange={(e) => setLeadId(e.target.value)}>
              <option value="">Myself ({user?.username})</option>
              {users
                .filter((u) => u.id !== user?.id)
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name || u.username} ({u.username})
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
            Create investigation
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
