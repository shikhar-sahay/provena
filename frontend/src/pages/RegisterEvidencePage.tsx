// Evidence registration form: file plus metadata, multipart upload.

import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { EvidenceType } from "../api/client";
import {
  EVIDENCE_TYPE_LABELS,
  buttonPrimaryClass,
  buttonSecondaryClass,
  formatBytes,
  inputClass,
  labelClass,
} from "../components/ui";

const TYPES: EvidenceType[] = ["log", "document", "image", "network", "email", "device", "archive", "other"];

export default function RegisterEvidencePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [evidenceType, setEvidenceType] = useState<EvidenceType>("log");
  const [source, setSource] = useState("");
  const [acquiredAt, setAcquiredAt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Select a file to register.");
      return;
    }
    if (!title.trim()) {
      setError("A title is required.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("title", title.trim());
      form.append("description", description.trim());
      form.append("evidence_type", evidenceType);
      form.append("source", source.trim());
      if (acquiredAt) form.append("acquired_at", new Date(acquiredAt).toISOString());
      const created = await api.registerEvidence(Number(id), form);
      navigate(`/investigations/${id}/evidence/${created.id}`, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not register evidence.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-lg font-semibold">Register evidence</h2>
      <p className="mt-1 text-sm text-slate-400">
        The file is stored under Provena control and a SHA-256 baseline is recorded.
      </p>

      <form
        onSubmit={(e) => void onSubmit(e)}
        className="mt-4 space-y-4 rounded-lg border border-slate-800 bg-slate-900 p-6"
      >
        <div>
          <label htmlFor="evidence-file" className={labelClass}>
            File
          </label>
          <input
            id="evidence-file"
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full text-sm text-slate-300 file:mr-3 file:rounded-md file:border file:border-slate-700 file:bg-slate-800 file:px-3 file:py-1.5 file:text-sm file:text-slate-200 hover:file:bg-slate-700"
          />
          {file && (
            <p className="mt-1 text-xs text-slate-500">
              {file.name} · {formatBytes(file.size)}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="evidence-title" className={labelClass}>
            Title
          </label>
          <input
            id="evidence-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={inputClass}
            placeholder="Perimeter firewall export, Jan 12-14"
            maxLength={255}
          />
        </div>

        <div>
          <label htmlFor="evidence-description" className={labelClass}>
            Description
          </label>
          <textarea
            id="evidence-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className={`${inputClass} min-h-24`}
            placeholder="What this evidence is and why it matters."
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="evidence-kind" className={labelClass}>
              Type
            </label>
            <select
              id="evidence-kind"
              value={evidenceType}
              onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
              className={inputClass}
            >
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {EVIDENCE_TYPE_LABELS[t]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="evidence-source" className={labelClass}>
              Source / origin
            </label>
            <input
              id="evidence-source"
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className={inputClass}
              placeholder="SIEM export, workstation ws-114"
              maxLength={255}
            />
          </div>
        </div>

        <div>
          <label htmlFor="evidence-acquired" className={labelClass}>
            Acquired at (optional)
          </label>
          <input
            id="evidence-acquired"
            type="datetime-local"
            value={acquiredAt}
            onChange={(e) => setAcquiredAt(e.target.value)}
            className={inputClass}
          />
        </div>

        {error && (
          <p role="alert" className="rounded-md bg-red-950 px-3 py-2 text-sm text-red-300">
            {error}
          </p>
        )}

        <div className="flex gap-3">
          <button type="submit" disabled={busy} className={buttonPrimaryClass}>
            {busy ? "Registering…" : "Register evidence"}
          </button>
          <button
            type="button"
            onClick={() => void navigate(`/investigations/${id}/evidence`)}
            className={buttonSecondaryClass}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
