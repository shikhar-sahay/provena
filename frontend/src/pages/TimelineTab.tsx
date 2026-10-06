// Investigation timeline tab: a deterministic record of what happened,
// assembled from lifecycle, evidence, integrity, and custody records.
// This is explicitly not AI timeline reconstruction.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { History } from "lucide-react";
import { api } from "../api/client";
import type { TimelineEntry } from "../api/client";
import { EmptyState, ErrorState, Skeleton } from "../components/StateViews";
import { actionErrorMessage } from "../lib/errors";
import { TimelineSpine } from "./EvidenceDetailPage";

export default function TimelineTab() {
  const { id } = useParams<{ id: string }>();
  const [entries, setEntries] = useState<TimelineEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .investigationTimeline(Number(id))
      .then((data) => {
        if (!cancelled) {
          setEntries(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(actionErrorMessage(err, "Could not load the timeline."));
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <ErrorState body={error} onRetry={() => window.location.reload()} />;

  return (
    <div className="max-w-3xl">
      <p className="text-sm text-ink2">
        Investigation activity in chronological order. This is a record of what
        happened, not an AI reconstruction.
      </p>
      <div className="mt-4 rounded-md border border-line bg-surface px-4 py-3">
        {!entries ? (
          <div className="space-y-3">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        ) : entries.length === 0 ? (
          <EmptyState
            icon={<History size={22} />}
            title="No timeline events yet"
            body="Lifecycle changes, evidence, verifications, and custody will appear here."
          />
        ) : (
          <TimelineSpine entries={entries} />
        )}
      </div>
    </div>
  );
}
