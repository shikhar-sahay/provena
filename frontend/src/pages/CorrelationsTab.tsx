// Correlations tab: shared entities across evidence, each expandable to the
// contributing artifact instances with provenance. No conclusions attached.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, Network } from "lucide-react";
import { api } from "../api/client";
import type { Correlation, CorrelationDetail } from "../api/client";
import { artifactTypeLabel, locatorLabel } from "../lib/analysis";
import { Badge } from "../components/Badge";
import { EmptyState, ErrorState, Skeleton } from "../components/StateViews";
import { actionErrorMessage } from "../lib/errors";

export default function CorrelationsTab({ invId }: { invId: number }) {
  const [items, setItems] = useState<Correlation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, CorrelationDetail>>({});

  const load = useCallback(async () => {
    try {
      setItems(await api.listCorrelations(invId));
      setError(null);
    } catch (err) {
      setError(actionErrorMessage(err, "Could not load correlations."));
    }
  }, [invId]);

  useEffect(() => {
    setItems(null);
    void load();
  }, [load]);

  async function toggle(id: number) {
    if (expanded === id) {
      setExpanded(null);
      return;
    }
    setExpanded(id);
    if (!details[id]) {
      try {
        const detail = await api.getCorrelation(invId, id);
        setDetails((current) => ({ ...current, [id]: detail }));
      } catch {
        // The card stays readable even if expansion fails.
      }
    }
  }

  if (error) return <ErrorState body={error} onRetry={() => void load()} />;
  if (items === null) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <EmptyState
        icon={<Network size={22} />}
        title="No cross-evidence correlations"
        body="A correlation appears when the same normalized entity is found in two or more distinct evidence items. Run analysis first, or add evidence with shared entities."
      />
    );
  }

  return (
    <ol className="space-y-3">
      {items.map((correlation) => {
        const isOpen = expanded === correlation.id;
        const detail = details[correlation.id];
        return (
          <li key={correlation.id} className="overflow-hidden rounded-md border border-line bg-surface">
            <button
              onClick={() => void toggle(correlation.id)}
              aria-expanded={isOpen}
              className="pv-transition w-full cursor-pointer px-4 py-3 text-left hover:bg-hover"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-semibold break-all">
                  {correlation.normalized_value}
                </span>
                <Badge tone="info">{artifactTypeLabel(correlation.artifact_type)}</Badge>
                <span className="ml-auto flex items-center gap-2 text-xs text-ink3">
                  {correlation.evidence_count} evidence · {correlation.artifact_count} artifacts
                  <ChevronDown
                    size={14}
                    aria-hidden="true"
                    className={`pv-transition ${isOpen ? "rotate-180" : ""}`}
                  />
                </span>
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {correlation.evidence_items.map((item) => (
                  <span
                    key={item.evidence_id}
                    className="rounded border border-line bg-canvas px-1.5 py-0.5 font-mono text-xs text-ink2"
                  >
                    {item.evidence_number}
                  </span>
                ))}
              </div>
            </button>
            {isOpen && (
              <div className="border-t border-line px-4 py-3">
                {!detail ? (
                  <Skeleton className="h-16" />
                ) : (
                  <ol className="space-y-2">
                    {detail.artifacts.map((artifact) => (
                      <li key={artifact.id} className="rounded-md border border-line px-3 py-2 text-sm">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            to={`/investigations/${invId}/evidence/${artifact.evidence_id}`}
                            className="font-mono text-xs text-accentink hover:underline"
                          >
                            {artifact.evidence_number}
                          </Link>
                          <span className="font-mono text-xs text-ink2">{locatorLabel(artifact.locator)}</span>
                          <span className="ml-auto text-xs text-ink3">
                            {artifact.extractor_name}-v{artifact.extractor_version}
                          </span>
                        </div>
                        {artifact.raw_value !== artifact.normalized_value && (
                          <p className="mt-0.5 font-mono text-xs text-ink3">
                            As observed: {artifact.raw_value}
                          </p>
                        )}
                        <p className="mt-1 rounded bg-canvas px-2 py-1.5 font-mono text-xs break-words">
                          {artifact.context}
                        </p>
                      </li>
                    ))}
                  </ol>
                )}
                <p className="mt-2 text-xs text-ink3">
                  Shared value across {correlation.evidence_count} evidence items. This is an
                  observed recurrence, not a conclusion.
                </p>
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
