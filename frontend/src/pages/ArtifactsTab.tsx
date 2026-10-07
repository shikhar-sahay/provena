// Artifacts tab: dense table with type/evidence/search filters, a pager,
// and a provenance drawer per artifact.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Boxes, Search } from "lucide-react";
import { api } from "../api/client";
import type { Artifact, ArtifactList, ArtifactType } from "../api/client";
import { ARTIFACT_TYPE_LABELS, artifactTypeLabel, locatorLabel } from "../lib/analysis";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Drawer } from "../components/Dialog";
import { Input, Select } from "../components/Field";
import { EmptyState, ErrorState, TableSkeleton } from "../components/StateViews";
import { useToast } from "../components/Toast";
import { actionErrorMessage } from "../lib/errors";

const TYPE_OPTIONS: (ArtifactType | "")[] = [
  "",
  "IP_ADDRESS",
  "EMAIL_ADDRESS",
  "USERNAME",
  "HOSTNAME",
  "DOMAIN",
  "FILE_PATH",
  "FILE_NAME",
  "HASH",
  "USB_DEVICE",
  "TIMESTAMP",
  "URL",
  "PORT",
  "MAC_ADDRESS",
  "PROCESS_NAME",
];

const PAGE_SIZE = 50;

export default function ArtifactsTab({ invId }: { invId: number }) {
  const { notify } = useToast();
  const [data, setData] = useState<ArtifactList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<ArtifactType | "">("");
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Artifact | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await api.listArtifacts(invId, {
        artifact_type: typeFilter || undefined,
        q: query || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setData(result);
      setError(null);
    } catch (err) {
      setError(actionErrorMessage(err, "Could not load artifacts."));
    }
  }, [invId, typeFilter, query, offset]);

  useEffect(() => {
    setData(null);
    void load();
  }, [load]);

  function applyFilters() {
    setOffset(0);
    setQuery(searchInput.trim());
  }

  return (
    <div className="space-y-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          applyFilters();
        }}
        className="flex flex-col gap-2 sm:flex-row"
      >
        <div className="relative min-w-0 flex-1 sm:max-w-xs">
          <Search
            size={14}
            className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-ink3"
          />
          <Input
            type="search"
            aria-label="Search artifacts"
            placeholder="Search normalized values…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-8"
          />
        </div>
        <Select
          aria-label="Filter by artifact type"
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value as ArtifactType | "");
            setOffset(0);
          }}
          className="sm:w-44"
        >
          {TYPE_OPTIONS.map((t) => (
            <option key={t || "all"} value={t}>
              {t ? ARTIFACT_TYPE_LABELS[t] : "All types"}
            </option>
          ))}
        </Select>
      </form>

      {error && <ErrorState body={error} onRetry={() => void load()} />}
      {data === null && !error && <TableSkeleton rows={6} />}
      {data !== null && data.total === 0 && (
        <EmptyState
          icon={<Boxes size={22} />}
          title="No artifacts yet"
          body="Run analysis over verified evidence. Extracted entities appear here with exact provenance."
        />
      )}
      {data !== null && data.total > 0 && (
        <>
          <div className="overflow-x-auto rounded-md border border-line">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <thead>
                <tr className="border-b border-line bg-surface text-[13px] text-ink2">
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">Value</th>
                  <th className="px-3 py-2 font-medium">Evidence</th>
                  <th className="px-3 py-2 font-medium">Source</th>
                  <th className="px-3 py-2 font-medium">Extraction</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line bg-surface">
                {data.items.map((item) => (
                  <tr key={item.id} className="pv-transition hover:bg-hover">
                    <td className="px-3 py-2 whitespace-nowrap text-ink2">
                      {artifactTypeLabel(item.artifact_type)}
                    </td>
                    <td className="max-w-xs px-3 py-2">
                      <button
                        onClick={() => setSelected(item)}
                        className="block max-w-full cursor-pointer truncate text-left font-mono text-[13px] font-medium text-ink hover:underline"
                        title={item.normalized_value}
                      >
                        {item.normalized_value}
                      </button>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs whitespace-nowrap text-ink2">
                      {item.evidence_number ?? `E-?`}
                    </td>
                    <td className="px-3 py-2 text-[13px] whitespace-nowrap text-ink2">
                      {locatorLabel(item.locator)}
                    </td>
                    <td className="px-3 py-2 text-[13px] whitespace-nowrap text-ink3">
                      {item.extractor_name}-v{item.extractor_version} · {item.method}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager total={data.total} offset={offset} onPage={setOffset} />
        </>
      )}

      <Drawer
        open={selected !== null}
        onClose={() => setSelected(null)}
        title={selected ? artifactTypeLabel(selected.artifact_type) : "Artifact"}
        description="Exact provenance for this extracted entity."
      >
        {selected && (
          <ArtifactDetail
            invId={invId}
            artifact={selected}
            notifyCopied={() => notify("success", "Source locator copied.")}
          />
        )}
      </Drawer>
    </div>
  );
}

function Pager({
  total,
  offset,
  onPage,
}: {
  total: number;
  offset: number;
  onPage: (offset: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const current = Math.floor(offset / PAGE_SIZE) + 1;
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between text-sm">
      <p className="text-ink3">
        {offset + 1} to {Math.min(offset + PAGE_SIZE, total)} of {total}
      </p>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={current <= 1} onClick={() => onPage(offset - PAGE_SIZE)}>
          Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={current >= pages}
          onClick={() => onPage(offset + PAGE_SIZE)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

export function ArtifactDetail({
  invId,
  artifact,
  notifyCopied,
}: {
  invId: number;
  artifact: Artifact;
  notifyCopied: () => void;
}) {
  async function copyLocator() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(artifact.locator));
      notifyCopied();
    } catch {
      // Clipboard may be unavailable; the locator remains visible as text.
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <Badge tone="neutral">{artifactTypeLabel(artifact.artifact_type)}</Badge>
        <p className="mt-2 font-mono text-sm break-all">{artifact.normalized_value}</p>
        {artifact.raw_value !== artifact.normalized_value && (
          <p className="mt-1 text-xs text-ink3">
            As observed: <span className="font-mono">{artifact.raw_value}</span>
          </p>
        )}
      </div>

      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-xs text-ink3">Evidence</dt>
          <dd className="mt-0.5">
            <Link
              to={`/investigations/${invId}/evidence/${artifact.evidence_id}`}
              className="font-mono text-[13px] text-accentink hover:underline"
            >
              {artifact.evidence_number ?? `Evidence #${artifact.evidence_id}`}
            </Link>
            {artifact.evidence_title && (
              <span className="ml-2 text-ink2">{artifact.evidence_title}</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink3">Source</dt>
          <dd className="mt-0.5 flex items-center justify-between gap-2">
            <span className="font-mono text-[13px]">{locatorLabel(artifact.locator)}</span>
            <button
              onClick={() => void copyLocator()}
              className="pv-transition shrink-0 cursor-pointer rounded px-1.5 py-0.5 text-xs font-medium text-accentink hover:bg-accentsoft"
            >
              Copy locator
            </button>
          </dd>
          <dd className="mt-0.5 font-mono text-xs break-all text-ink3">
            {JSON.stringify(artifact.locator)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink3">Context</dt>
          <dd className="mt-0.5 rounded-md border border-line bg-canvas px-2.5 py-2 font-mono text-xs break-words">
            {artifact.context}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink3">Extraction</dt>
          <dd className="mt-0.5 text-[13px]">
            {artifact.extractor_name}-v{artifact.extractor_version} · {artifact.method}
          </dd>
          <dd className="text-xs text-ink3">Deterministic; no confidence score attached.</dd>
        </div>
      </dl>
    </div>
  );
}
