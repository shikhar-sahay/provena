// Evidence registration form: file plus metadata over multipart upload.
// Used inside the registration drawer and the deep-link register page.

import { useRef, useState } from "react";
import type { DragEvent, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { FileUp } from "lucide-react";
import { api } from "../api/client";
import type { EvidenceType } from "../api/client";
import { useToast } from "./Toast";
import { Button } from "./Button";
import { EVIDENCE_TYPE_LABELS } from "./Badge";
import { Field, Input, Select, Textarea } from "./Field";
import { actionErrorMessage } from "../lib/errors";
import { formatBytes } from "../lib/format";

const TYPES: EvidenceType[] = ["log", "document", "image", "network", "email", "device", "archive", "other"];

export function RegisterEvidenceForm({
  invId,
  onDone,
  navigateOnSuccess = false,
}: {
  invId: number;
  onDone: () => void;
  navigateOnSuccess?: boolean;
}) {
  const { notify } = useToast();
  const navigate = useNavigate();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [evidenceType, setEvidenceType] = useState<EvidenceType>("log");
  const [source, setSource] = useState("");
  const [acquiredAt, setAcquiredAt] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function pick(files: FileList | null) {
    const next = files?.[0] ?? null;
    setFile(next);
    setFileError(null);
    if (next && !title.trim()) {
      setTitle(next.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " "));
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    pick(event.dataTransfer.files);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    let valid = true;
    if (!file) {
      setFileError("Select a file to register.");
      valid = false;
    }
    if (!title.trim()) {
      setTitleError("A title is required.");
      valid = false;
    } else {
      setTitleError(null);
    }
    if (!valid) return;
    setError(null);
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file as File);
      form.append("title", title.trim());
      form.append("description", description.trim());
      form.append("evidence_type", evidenceType);
      form.append("source", source.trim());
      if (acquiredAt) form.append("acquired_at", new Date(acquiredAt).toISOString());
      const created = await api.registerEvidence(invId, form);
      notify("success", `Evidence ${created.evidence_number} registered. Baseline recorded.`);
      if (navigateOnSuccess) {
        navigate(`/investigations/${invId}/evidence/${created.id}`, { replace: true });
      } else {
        onDone();
      }
    } catch (err) {
      setError(actionErrorMessage(err, "Could not register evidence."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
      <div>
        <span id="evidence-file-label" className="mb-1 block text-[13px] font-medium text-ink2">
          File
        </span>
        <div
          role="button"
          tabIndex={0}
          aria-labelledby="evidence-file-label"
          onClick={() => fileInput.current?.click()}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") fileInput.current?.click();
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`pv-transition flex cursor-pointer flex-col items-center rounded-md border border-dashed px-4 py-6 text-center ${
            dragging ? "border-accent bg-accentsoft" : "border-linestrong hover:border-ink3 hover:bg-hover"
          }`}
        >
          <FileUp size={20} className="text-ink3" />
          <p className="mt-2 text-sm font-medium">
            {file ? file.name : "Drop a file here, or click to browse"}
          </p>
          <p className="mt-0.5 text-xs text-ink3">
            {file ? formatBytes(file.size) : "Stored under Provena control; original name kept as metadata."}
          </p>
          <input
            ref={fileInput}
            type="file"
            aria-label="Evidence file"
            className="sr-only"
            onChange={(e) => pick(e.target.files)}
          />
        </div>
        {fileError && (
          <p role="alert" className="mt-1 text-[13px] text-danger-ink">
            {fileError}
          </p>
        )}
      </div>

      <Field label="Title" htmlFor="reg-title" error={titleError}>
        <Input
          id="reg-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Perimeter firewall export, Jan 12-14"
          maxLength={255}
        />
      </Field>
      <Field label="Description" htmlFor="reg-description">
        <Textarea
          id="reg-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What this evidence is and why it matters."
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Type" htmlFor="reg-type">
          <Select id="reg-type" value={evidenceType} onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {EVIDENCE_TYPE_LABELS[t]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Source / origin" htmlFor="reg-source">
          <Input
            id="reg-source"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="SIEM export, workstation ws-114"
            maxLength={255}
          />
        </Field>
      </div>
      <Field label="Acquired at (optional)" htmlFor="reg-acquired">
        <Input
          id="reg-acquired"
          type="datetime-local"
          value={acquiredAt}
          onChange={(e) => setAcquiredAt(e.target.value)}
        />
      </Field>

      {error && (
        <p role="alert" className="rounded-md border border-danger-line bg-danger-bg px-3 py-2 text-sm text-danger-ink">
          {error}
        </p>
      )}

      <div className="flex justify-end">
        <Button variant="primary" type="submit" loading={busy}>
          Register evidence
        </Button>
      </div>
    </form>
  );
}
