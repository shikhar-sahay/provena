import type { IntegrityStatus } from "../api/client";
import { Button } from "./Button";

export function EvidenceStatus({ registration = "ready", integrity, onRecover, busy = false }: {
  registration?: "pending" | "failed" | "ready";
  integrity: IntegrityStatus;
  onRecover?: () => void;
  busy?: boolean;
}) {
  if (registration !== "ready") return <div role="alert" className="mt-3 rounded-md border border-line bg-surface p-3 text-sm">
    <p>Registration {registration}. This item is not eligible for verification or analysis.</p>
    <p className="mt-1 text-ink2">Retry the same upload if interrupted. Recovery checks retained bytes against the original baseline.</p>
    {onRecover && <Button variant="secondary" size="sm" loading={busy} onClick={onRecover}>Recover registration</Button>}
  </div>;
  const messages: Record<IntegrityStatus, string> = {
    not_verified: "Registered successfully. Verify integrity before analysis.",
    verified: "Last check matched the baseline. Analysis checks a private copy again before parsing.",
    mismatch: "Integrity mismatch. Preserve this item and investigate the change; do not replace its baseline.",
    unavailable: "Storage unavailable. Ask an operator to restore the original bytes, then verify again.",
  };
  return <p role="status" className="mt-3 text-sm text-ink2">{messages[integrity]}</p>;
}
