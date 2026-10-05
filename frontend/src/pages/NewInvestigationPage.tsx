// Create investigation form: title, description, priority, optional lead.

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { Priority, User } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import {
  buttonPrimaryClass,
  buttonSecondaryClass,
  inputClass,
  labelClass,
} from "../components/ui";

const PRIORITIES: Priority[] = ["low", "medium", "high", "critical"];

export default function NewInvestigationPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [leadId, setLeadId] = useState<string>("");
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
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
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setError("A title is required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const created = await api.createInvestigation({
        title: title.trim(),
        description: description.trim(),
        priority,
        lead_investigator_id: leadId ? Number(leadId) : undefined,
      });
      navigate(`/investigations/${created.id}`, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the investigation.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight">New investigation</h1>
      <p className="mt-1 text-sm text-slate-400">
        Open a new investigation. A case number is assigned automatically.
      </p>

      <form
        onSubmit={(e) => void onSubmit(e)}
        className="mt-6 space-y-4 rounded-lg border border-slate-800 bg-slate-900 p-6"
      >
        <div>
          <label htmlFor="title" className={labelClass}>
            Title
          </label>
          <input
            id="title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputClass}
            placeholder="Suspected data exfiltration, Q3 vendor review"
            maxLength={255}
          />
        </div>

        <div>
          <label htmlFor="description" className={labelClass}>
            Description
          </label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={`${inputClass} min-h-28`}
            placeholder="Background, scope, and initial observations."
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="priority" className={labelClass}>
              Priority
            </label>
            <select
              id="priority"
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
            <label htmlFor="lead" className={labelClass}>
              Lead investigator
            </label>
            <select
              id="lead"
              value={leadId}
              onChange={(e) => setLeadId(e.target.value)}
              className={inputClass}
            >
              <option value="">Myself ({user?.username})</option>
              {users
                .filter((u) => u.id !== user?.id)
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name || u.username} ({u.username})
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

        <div className="flex gap-3">
          <button type="submit" disabled={busy} className={buttonPrimaryClass}>
            {busy ? "Creating…" : "Create investigation"}
          </button>
          <button
            type="button"
            onClick={() => void navigate("/investigations")}
            className={buttonSecondaryClass}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
