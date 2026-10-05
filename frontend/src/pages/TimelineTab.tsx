// Investigation timeline tab: deterministic narrative assembled from real records.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { TimelineEntry } from "../api/client";
import { ErrorBlock } from "./DashboardPage";
import { TimelineList } from "./EvidenceDetailPage";

export default function TimelineTab() {
  const { id } = useParams<{ id: string }>();
  const [entries, setEntries] = useState<TimelineEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .investigationTimeline(Number(id))
      .then((data) => {
        if (!cancelled) setEntries(data);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Could not load the timeline.");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <ErrorBlock message={error} />;

  return (
    <div>
      <h2 className="text-lg font-semibold">Timeline</h2>
      <p className="mt-1 text-sm text-slate-400">
        Investigation activity in chronological order: lifecycle, evidence,
        integrity checks, and custody. This is a record of what happened, not an
        AI reconstruction.
      </p>
      <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900 p-5">
        {!entries ? (
          <p className="text-sm text-slate-500">Loading timeline…</p>
        ) : (
          <TimelineList entries={entries} />
        )}
      </div>
    </div>
  );
}
