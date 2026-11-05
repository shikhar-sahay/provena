import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router-dom";
import { api, eventApi } from "../api/client";
import type { Evidence, EventPage, EventProfile, EventProfileConfig, EventRunPage, SecurityEvent } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Button } from "../components/Button";
import { Drawer } from "../components/Dialog";
import { Field, Input, Select } from "../components/Field";
import { EmptyState, ErrorState, TableSkeleton } from "../components/StateViews";
import { EventProfileForm } from "../components/EventProfileForm";
import { EventCoverageView } from "../components/EventCoverageView";
import { actionErrorMessage } from "../lib/errors";
import type { WorkspaceContext } from "./InvestigationWorkspace";

const initialFilters = { category: "", event_type: "", outcome: "", username: "", host: "", source_ip: "", destination_ip: "", provider: "", event_id: "", evidence_id: "", profile_id: "", run_id: "", start: "", end: "" };

export default function EventsPage() {
  const { id } = useParams<{ id: string }>();
  const { inv, canManage, archivedLocked } = useOutletContext<WorkspaceContext>();
  const { user } = useAuth();
  const canIngest = !archivedLocked && (canManage || user?.role === "forensic_analyst");
  return <EventExplorer key={id} invId={Number(id)} canIngest={canIngest} caseTitle={inv.title} />;
}

export function EventExplorer({ invId, canIngest, caseTitle = "Investigation" }: { invId: number; canIngest: boolean; caseTitle?: string }) {
  const [profiles, setProfiles] = useState<EventProfile[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [runs, setRuns] = useState<EventRunPage | null>(null);
  const [data, setData] = useState<EventPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState("");
  const [selectedProfile, setSelectedProfile] = useState("");
  const [draft, setDraft] = useState(initialFilters);
  const [filters, setFilters] = useState(initialFilters);
  const [offset, setOffset] = useState(0);
  const [runOffset, setRunOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [detail, setDetail] = useState<SecurityEvent | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const generation = useRef(0);

  const load = useCallback(async () => {
    const request = ++generation.current;
    setData(null);
    try {
      const [p, e, r, events] = await Promise.all([eventApi.profiles(invId), api.listEvidence(invId), eventApi.runs(invId, runOffset), eventApi.list(invId, filters, offset)]);
      if (request !== generation.current) return;
      setProfiles(p); setEvidence(e); setRuns(r); setData(events); setError(null);
    } catch (err) {
      if (request === generation.current) setError(actionErrorMessage(err, "Could not load security events."));
    }
  }, [invId, filters, offset, runOffset]);
  useEffect(() => { void load(); return () => { generation.current++; }; }, [load, refresh]);

  async function saveProfile(name: string, config: EventProfileConfig) {
    setBusy(true); setActionError(null);
    try {
      const saved = await eventApi.createProfile(invId, name, config);
      setSelectedProfile(String(saved.id)); setProfileOpen(false); setRefresh((n) => n + 1);
      setNotice("Immutable profile saved. Select verified evidence and ingest it.");
    } catch (err) { setActionError(actionErrorMessage(err, "Could not save the source profile.")); }
    finally { setBusy(false); }
  }
  async function ingest() {
    setBusy(true); setActionError(null); setNotice(null);
    try {
      const run = await eventApi.ingest(invId, Number(selectedEvidence), Number(selectedProfile));
      setNotice(`Ingestion #${run.id}: ${run.status}. Recognized ${run.coverage.recognized ?? 0}; new events ${run.coverage.events_created ?? 0}.`);
      setRunOffset(0); setRefresh((n) => n + 1);
    } catch (err) { setActionError(actionErrorMessage(err, "Could not ingest events.")); }
    finally { setBusy(false); }
  }
  async function openEvent(key: string) {
    setDetailError(null);
    try { setDetail(await eventApi.detail(invId, key)); }
    catch (err) { setDetailError(actionErrorMessage(err, "Could not load event provenance.")); }
  }
  async function recover(run: number) {
    setBusy(true);
    try { await eventApi.recover(invId, run); setRefresh((n) => n + 1); }
    catch (err) { setActionError(actionErrorMessage(err, "Could not close interrupted ingestion.")); }
    finally { setBusy(false); }
  }
  const selected = evidence.find((e) => String(e.id) === selectedEvidence);
  const eligible = selected?.integrity_status === "verified" && selected.registration_status === "ready";
  return <div className="space-y-4">
    <div><h2 className="text-lg font-semibold">Security events: {caseTitle}</h2><p className="text-sm text-ink2">Normalized observations, not detections. Historical interpretations are preserved. Filter by profile or run to select one event set.</p></div>
    {canIngest && <section className="space-y-3 rounded-md border border-line p-4" aria-label="Event ingestion">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Evidence to ingest" htmlFor="ingest-evidence"><Select id="ingest-evidence" value={selectedEvidence} onChange={(e) => setSelectedEvidence(e.target.value)}><option value="">Select evidence</option>{evidence.map((e) => <option key={e.id} value={e.id}>{e.evidence_number}: {e.title} ({e.registration_status}, {e.integrity_status})</option>)}</Select></Field>
        <Field label="Source interpretation profile" htmlFor="ingest-profile"><Select id="ingest-profile" value={selectedProfile} onChange={(e) => setSelectedProfile(e.target.value)}><option value="">Select profile</option>{profiles.map((p) => <option key={p.id} value={p.id}>{p.name}: {p.configuration.adapter} / {p.configuration.format}</option>)}</Select></Field>
      </div>
      {selectedProfile && <details className="text-xs text-ink2"><summary>Selected immutable profile configuration</summary><pre className="overflow-auto">{JSON.stringify(profiles.find((p) => String(p.id) === selectedProfile), null, 2)}</pre></details>}
      {selectedEvidence && !eligible && <p className="text-sm text-warning-ink">Ready registration and independent verification are required. <Link className="underline" to={`/investigations/${invId}/evidence/${selectedEvidence}`}>Open evidence to verify or recover it.</Link></p>}
      <div className="flex flex-wrap gap-2"><Button disabled={!eligible || !selectedProfile || busy} loading={busy} onClick={() => void ingest()}>Ingest verified evidence</Button><Button variant="secondary" onClick={() => setProfileOpen((v) => !v)}>Configure source profile</Button><Link className="text-sm underline" to={`/investigations/${invId}/evidence/register`}>Register evidence</Link></div>
      <p className="text-xs text-ink3">Supported: Linux auth.log/secure/sshd text and named Windows Security/Sysmon JSON, JSONL or CSV exports. Binary EVTX, XML, OCR and arbitrary schemas are unsupported.</p>
    </section>}
    {actionError && <p role="alert" className="text-sm text-danger-ink">{actionError}</p>}
    {notice && <p role="status" className="text-sm text-ink2">{notice}</p>}
    {profileOpen && canIngest && <EventProfileForm save={saveProfile} busy={busy} />}
    <form className="space-y-3 rounded-md border border-line p-4" aria-label="Event filters" onSubmit={(e) => { e.preventDefault(); setOffset(0); setFilters({ ...draft }); }}>
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <Field label="Category" htmlFor="filter-category"><Select id="filter-category" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}><option value="">All categories</option>{["authentication", "session", "account", "process", "network"].map((c) => <option key={c}>{c}</option>)}</Select></Field>
        <Field label="Outcome" htmlFor="filter-outcome"><Select id="filter-outcome" value={draft.outcome} onChange={(e) => setDraft({ ...draft, outcome: e.target.value })}><option value="">All outcomes</option><option value="failure">Failure</option><option value="success">Success</option><option value="unknown">Unknown / context</option></Select></Field>
        {([['username', 'Account'], ['host', 'Host'], ['source_ip', 'Source IP'], ['destination_ip', 'Destination IP'], ['provider', 'Provider'], ['event_type', 'Event type'], ['event_id', 'Provider Event ID'], ['evidence_id', 'Evidence ID'], ['profile_id', 'Profile ID'], ['run_id', 'Run ID'], ['start', 'UTC range start (offset required)'], ['end', 'UTC range end (offset required)']] as const).map(([key, label]) => <Field key={key} label={label} htmlFor={`filter-${key}`}><Input id={`filter-${key}`} maxLength={key === 'provider' ? 100 : 256} placeholder={key === 'start' || key === 'end' ? '2026-11-05T00:00:00Z' : undefined} value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} /></Field>)}
      </div><Button type="submit">Apply event filters</Button>
    </form>
    {error && <ErrorState body={error} onRetry={() => void load()} />}
    {detailError && <p role="alert" className="text-danger-ink">{detailError}</p>}
    {!data && !error && <TableSkeleton rows={5} />}
    {data && <>
      <p className="text-xs text-ink3">{data.time_policy} {data.view_policy}</p>
      {data.total === 0 ? <EmptyState title="No matching security events" body="Ingest verified supported logs or adjust filters. Artifact analysis alone does not create normalized events." /> : <div className="overflow-x-auto rounded-md border border-line"><table className="w-full min-w-[65rem] text-left text-sm"><thead className="bg-surface text-xs text-ink2"><tr>{['Source time', 'Provider / type', 'Outcome', 'Account / host', 'Source / destination', 'Evidence', 'Provenance'].map((h) => <th className="p-3" key={h}>{h}</th>)}</tr></thead><tbody className="divide-y divide-line">{data.items.map((e) => <tr key={e.semantic_key}><td className="p-3 font-mono text-xs">{e.original_timestamp ?? 'Missing timestamp'}<span className="block text-ink3">{e.time_semantics.certainty}</span></td><td className="p-3">{e.provider}<span className="block text-xs text-ink3">{e.category} / {e.event_type}{e.event_id && ` (${e.event_id})`}</span></td><td className="p-3">{e.outcome}</td><td className="p-3">{e.username ?? 'Unknown account'}<span className="block text-xs">{e.hostname ?? 'Unknown host'}</span></td><td className="p-3 font-mono text-xs">{e.source_ip ?? '-'}<span className="block">{e.destination_ip ?? '-'}</span></td><td className="p-3"><Link className="underline" to={`/investigations/${invId}/evidence/${e.evidence_id}`}>{e.evidence_number}</Link>{!e.support_verified && <p className="text-xs text-warning-ink">Historical: support is not currently verified</p>}</td><td className="p-3"><Button size="sm" variant="secondary" onClick={() => void openEvent(e.semantic_key)}>Inspect event</Button></td></tr>)}</tbody></table></div>}
      <div className="flex items-center gap-3 text-sm"><span>{data.total} events; showing {data.total ? offset + 1 : 0}-{Math.min(offset + 50, data.total)}</span><Button variant="secondary" disabled={offset === 0} onClick={() => setOffset((n) => Math.max(0, n - 50))}>Previous events</Button><Button variant="secondary" disabled={offset + 50 >= data.total} onClick={() => setOffset((n) => n + 50)}>Next events</Button></div>
    </>}
    <section aria-label="Ingestion history" className="space-y-2"><h3 className="text-sm font-semibold">Ingestion status and record coverage</h3>{runs?.items.map((r) => <div key={r.id}><EventCoverageView run={r} />{canIngest && r.status === "running" && <Button size="sm" disabled={busy} onClick={() => void recover(r.id)}>Close interrupted run #{r.id}</Button>}</div>)}{runs && <div className="flex gap-2"><Button variant="secondary" disabled={runOffset === 0} onClick={() => setRunOffset((n) => Math.max(0, n - 25))}>Newer runs</Button><Button variant="secondary" disabled={runOffset + 25 >= runs.total} onClick={() => setRunOffset((n) => n + 25)}>Older runs</Button></div>}</section>
    <Drawer open={detail !== null} onClose={() => setDetail(null)} title="Normalized event provenance" description="Immutable interpretation of one verified source record.">{detail && <EventDetail event={detail} invId={invId} />}</Drawer>
  </div>;
}

export function EventDetail({ event, invId }: { event: SecurityEvent; invId: number }) {
  return <div className="space-y-3 text-sm">
    <Link className="underline" to={`/investigations/${invId}/evidence/${event.evidence_id}`}>Open source evidence {event.evidence_number}</Link>
    {!event.support_verified && <p role="alert" className="text-warning-ink">Historical event: underlying evidence is not currently verified.</p>}
    <p>Original timestamp: {event.original_timestamp ?? 'Missing'}</p><p>UTC projection: {event.timestamp_utc ?? 'Not established'}</p><p>Time certainty: {event.time_semantics.certainty}; precision: {event.time_semantics.precision ?? 'unknown'}.</p>
    <p>Coverage: {event.coverage_status}. Run #{event.first_run_id}; adapter {event.adapter_version}; normalization {event.normalization_version}.</p>
    {event.warnings.map((w, i) => <p key={i} className="text-warning-ink">{w}</p>)}
    <dl className="space-y-3">{Object.entries({ 'Stable event identity': event.semantic_key, 'Input SHA-256': event.input_sha256, 'Record fingerprint': event.record_fingerprint, 'Source locator': event.locator, 'Source interpretation': event.profile_snapshot, 'Time assumptions': event.time_semantics.assumptions, 'Event-specific attributes': event.attributes }).map(([key, value]) => <div key={key}><dt className="font-semibold">{key}</dt><dd className="mt-1 whitespace-pre-wrap break-all font-mono text-xs">{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</dd></div>)}</dl>
  </div>;
}
