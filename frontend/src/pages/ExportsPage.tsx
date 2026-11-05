import { useCallback, useEffect, useRef, useState } from 'react';
import { useOutletContext, useParams } from 'react-router-dom';
import { api, authenticationApi, exportApi } from '../api/client';
import type { Evidence, Report, InvestigationEventSet, InvestigationExport, ExportSelection } from '../api/client';
import { Button } from '../components/Button';
import { Field, Select } from '../components/Field';
import { EmptyState, ErrorState } from '../components/StateViews';
import { actionErrorMessage } from '../lib/errors';
import type { WorkspaceContext } from './InvestigationWorkspace';

export default function ExportsPage() {
  const { id } = useParams(); const { canManage } = useOutletContext<WorkspaceContext>();
  return <ExportWorkbench key={id} invId={Number(id)} canExportOriginals={canManage} />;
}

export function ExportWorkbench({ invId, canExportOriginals }: { invId: number; canExportOriginals: boolean }) {
  const [evidence, setEvidence] = useState<Evidence[]>([]); const [reports, setReports] = useState<Report[]>([]);
  const [sets, setSets] = useState<InvestigationEventSet[]>([]); const [history, setHistory] = useState<InvestigationExport[]>([]);
  const [mode, setMode] = useState<'metadata' | 'originals'>('metadata');
  const [setIds, setSetIds] = useState<number[]>([]); const [reportIds, setReportIds] = useState<number[]>([]);
  const [evidenceIds, setEvidenceIds] = useState<number[]>([]); const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false); const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null); const [notice, setNotice] = useState('');
  const generation = useRef(0); const request = useRef<{ signature: string; key: string } | null>(null);
  const load = useCallback(async () => {
    const sequence = ++generation.current; setLoading(true); setError(null); setHistory([]);
    try {
      const [e, r, s, h] = await Promise.all([api.listEvidence(invId), api.listReports(invId), authenticationApi.sets(invId), exportApi.list(invId, offset)]);
      if (sequence !== generation.current) return;
      setEvidence(e); setReports(r); setSets(s); setHistory(h);
    } catch (err) { if (sequence === generation.current) setError(actionErrorMessage(err, 'Could not load investigation exports.')); }
    finally { if (sequence === generation.current) setLoading(false); }
  }, [invId, offset]);
  useEffect(() => { void load(); return () => { generation.current++; }; }, [load]);
  function toggle(values: number[], id: number, checked: boolean) { return checked ? [...values, id].sort((a, b) => a - b) : values.filter(v => v !== id); }
  async function create() {
    const selection: ExportSelection = { mode, event_set_ids: setIds, report_ids: reportIds, evidence_ids: mode === 'originals' ? evidenceIds : [] };
    const signature = JSON.stringify(selection);
    if (request.current?.signature !== signature) request.current = { signature, key: crypto.randomUUID() };
    setBusy(true); setError(null);
    try {
      const result = await exportApi.create(invId, selection, request.current.key);
      setNotice(`Export #${result.id}: ${result.status}. ${result.error ?? 'Inspect the package summary before downloading.'}`);
      request.current = null; await load();
    } catch (err) { setError(actionErrorMessage(err, 'Could not confirm export creation. Reload history before retrying; retrying this selection reuses its request key.')); }
    finally { setBusy(false); }
  }
  async function operation(work: () => Promise<void>) {
    setBusy(true); setError(null);
    try { await work(); }
    catch (err) { setError(actionErrorMessage(err, 'Export operation failed. Reload history and inspect its status.')); }
    finally { setBusy(false); }
  }
  return <div className="space-y-5">
    <header><h2 className="text-xl font-semibold">Investigation exports</h2><p className="text-sm text-ink2">Create a versioned forensic package with traceable selections, SHA-256 manifest and immutable reports.</p></header>
    {error && <ErrorState body={error} onRetry={() => void load()} />}
    {notice && <p role="status" className="text-sm">{notice}</p>}
    <section className="space-y-3 rounded-lg border border-line p-4">
      <Field label="Export mode" htmlFor="export-mode"><Select id="export-mode" disabled={busy} value={mode} onChange={e => setMode(e.target.value as 'metadata' | 'originals')}><option value="metadata">Metadata only, no original evidence bytes</option>{canExportOriginals && <option value="originals">Include explicitly selected verified originals</option>}</Select></Field>
      <p className="text-xs text-ink2">All packages include the authorized case inventory, custody and audit metadata, source profiles and artifact history. Normalized events and detections follow selected event sets. Reports retain their original hashes. Metadata can still contain confidential accounts, IPs, annotations and source excerpts.</p>
      <fieldset disabled={busy || loading} className="space-y-2"><legend className="font-medium text-sm">Normalized event sets (maximum 20)</legend>{sets.map(s => <label key={s.id} className="flex gap-2 text-sm"><input type="checkbox" checked={setIds.includes(s.id)} onChange={e => setSetIds(toggle(setIds, s.id, e.target.checked))} />{s.name} · {s.coverage.included_events} events · {s.coverage.partial ? 'partial' : 'declared complete'} coverage</label>)}</fieldset>
      <fieldset disabled={busy || loading} className="space-y-2"><legend className="font-medium text-sm">Immutable reports (maximum 100)</legend>{reports.map(r => <label key={r.id} className="flex gap-2 text-sm"><input type="checkbox" checked={reportIds.includes(r.id)} onChange={e => setReportIds(toggle(reportIds, r.id, e.target.checked))} />Report #{r.report_number} · {r.content_sha256.slice(0, 16)}</label>)}</fieldset>
      {mode === 'originals' && <fieldset disabled={busy || loading} className="space-y-2"><legend className="font-medium text-sm">Original evidence, fresh verification required (maximum 100)</legend>{evidence.map(e => <label key={e.id} className="flex gap-2 text-sm"><input type="checkbox" checked={evidenceIds.includes(e.id)} disabled={e.registration_status !== 'ready' || e.integrity_status !== 'verified'} onChange={event => setEvidenceIds(toggle(evidenceIds, e.id, event.target.checked))} />{e.evidence_number} · {e.title} · {e.integrity_status} · {e.file_size} bytes</label>)}<p role="alert" className="text-xs">Selected originals leave the platform when downloaded. Protect the package as confidential investigative evidence. Any missing or changed original blocks package completion.</p></fieldset>}
      <p className="text-sm">Selection: {setIds.length} event sets, {reportIds.length} reports, {mode === 'originals' ? evidenceIds.length : 0} original evidence files. Default server limit: 512 MiB per package and 32 MiB metadata.</p>
      <Button disabled={busy || loading || setIds.length > 20 || reportIds.length > 100 || evidenceIds.length > 100 || (mode === 'originals' && !evidenceIds.length)} onClick={() => void create()}>{busy ? 'Preparing verified package...' : 'Create export snapshot'}</Button>
      <p className="text-xs text-ink2">Preparation is synchronous with a durable operation record, not a percentage-based background job. Packages expire under server retention policy, 24 hours by default. Interrupted attempts remain visible and can be recovered by a case manager.</p>
    </section>
    <section className="space-y-3"><h3 className="font-semibold">Export history</h3>{loading ? <p role="status">Loading exports...</p> : !history.length ? <EmptyState title="No exports on this page" body="Choose a metadata-only package or explicitly select verified originals." /> : history.map(item => <article key={item.id} className="space-y-2 rounded-lg border border-line p-4">
      <p className="font-medium">Export #{item.id} · {item.mode} · {item.status}</p><p className="text-sm">{item.byte_size ?? 'Unknown'} bytes · {item.manifest_summary.files ?? 'Unknown'} files</p>
      {item.error && <p role="alert" className="text-sm">{item.error}</p>}
      {item.package_sha256 && <p className="break-all font-mono text-xs">Package SHA-256: {item.package_sha256}</p>}
      {item.manifest_summary.warnings?.map(w => <p key={w} className="text-xs text-ink2">{w}</p>)}
      <Button disabled={busy || item.status !== 'completed' || (item.mode === 'originals' && !canExportOriginals)} onClick={() => void operation(async () => { await exportApi.download(invId, item); setNotice(`Export #${item.id} downloaded. Verify it offline before relying on its contents.`); })}>Download export #{item.id}</Button>
      {canExportOriginals && (item.status === 'running' || item.status === 'completed' || item.manifest_summary.cleanup_pending) && <Button disabled={busy} onClick={() => void operation(async () => { await exportApi.recover(invId, item.id); await load(); setNotice('Recovery checked. Active work is serialized; interrupted attempts, pending cleanup and expired packages are handled.'); })}>Recover interrupted or prune expired #{item.id}</Button>}
    </article>)}<nav aria-label="Export history pagination" className="flex gap-3"><Button disabled={busy || offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous exports</Button><Button disabled={busy || history.length < 25} onClick={() => setOffset(offset + 25)}>Next exports</Button></nav></section>
    <section className="rounded-lg border border-line p-4 text-sm"><h3 className="font-semibold">Verify offline</h3><p>From the backend source directory, run:</p><code className="block break-all py-2">python -m app.ops.archive provena-case-{invId}-export-ID.zip</code><p>The verifier never extracts or executes content. It checks structure, limits, every file digest and embedded report hashes. A passing unsigned manifest proves internal integrity consistency; it does not prove authenticity, independent provenance or forensic certification.</p></section>
  </div>;
}
