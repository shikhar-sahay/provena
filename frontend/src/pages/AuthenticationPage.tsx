import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useOutletContext, useParams } from 'react-router-dom';
import { api, authenticationApi, eventApi } from '../api/client';
import type { AuthenticationRun, EventRunPage, Finding, InvestigationEventSet, SecurityEvent, Evidence, EventProfile } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/Button';
import { Field, Input, Select, Textarea } from '../components/Field';
import { Drawer } from '../components/Dialog';
import { EmptyState, ErrorState } from '../components/StateViews';
import { EventDetail } from './EventsPage';
import { actionErrorMessage } from '../lib/errors';
import type { WorkspaceContext } from './InvestigationWorkspace';

const emptyFilters = { lane: 'utc', username: '', account_domain: '', domain_missing: '', provider: '', host: '', source_ip: '', outcome: '', event_type: '', start: '', end: '', finding_id: '' };
type Timeline = Awaited<ReturnType<typeof authenticationApi.timeline>>;

export default function AuthenticationPage() {
  const { id } = useParams();
  const { canManage, archivedLocked } = useOutletContext<WorkspaceContext>();
  const { user } = useAuth();
  return <AuthenticationWorkbench key={id} invId={Number(id)} canProduce={!archivedLocked && (canManage || user?.role === 'forensic_analyst')} canReview={!archivedLocked && canManage} />;
}

export function AuthenticationWorkbench({ invId, canProduce, canReview }: { invId: number; canProduce: boolean; canReview: boolean }) {
  const [sets, setSets] = useState<InvestigationEventSet[]>([]);
  const [setId, setSetId] = useState(0);
  const [sources, setSources] = useState<EventRunPage | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [profiles, setProfiles] = useState<EventProfile[]>([]);
  const [sourceOffset, setSourceOffset] = useState(0);
  const [selectedRuns, setSelectedRuns] = useState<number[]>([]);
  const [name, setName] = useState('Authentication investigation');
  const [runs, setRuns] = useState<AuthenticationRun[]>([]);
  const [runTotal, setRunTotal] = useState(0);
  const [runOffset, setRunOffset] = useState(0);
  const [runId, setRunId] = useState(0);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [findingTotal, setFindingTotal] = useState(0);
  const [findingOffset, setFindingOffset] = useState(0);
  const [detail, setDetail] = useState<Finding | null>(null);
  const [contextFinding, setContextFinding] = useState<Finding | null>(null);
  const [history, setHistory] = useState<Awaited<ReturnType<typeof authenticationApi.history>>>([]);
  const [notes, setNotes] = useState<Awaited<ReturnType<typeof api.listNotes>>>([]);
  const [note, setNote] = useState('');
  const [filters, setFilters] = useState(emptyFilters);
  const [draft, setDraft] = useState(emptyFilters);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [offset, setOffset] = useState(0);
  const [event, setEvent] = useState<SecurityEvent | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [windowSeconds, setWindowSeconds] = useState(300);
  const [minFailures, setMinFailures] = useState(5);
  const [minAccounts, setMinAccounts] = useState(5);
  const [allowAssumed, setAllowAssumed] = useState(false);
  const [grouping, setGrouping] = useState('account_host');
  const [advanced, setAdvanced] = useState({ spray_max_per_account: 3, lockout_min_events: 3, lockout_min_accounts: 2,
    burst_min_attempts: 20, burst_min_accounts: 3, burst_min_failure_fraction: 0.5, clock_uncertainty_seconds: 1, result_limit: 100 });
  const generation = useRef(0);
  const historyGeneration = useRef(0);
  const closeFinding = useCallback(() => { historyGeneration.current++; setDetail(null); }, []);
  const closeEvent = useCallback(() => setEvent(null), []);
  const selected = sets.find(s => s.id === setId);
  const activeRun = runs.find(r => r.id === runId);

  const load = useCallback(async () => {
    const request = ++generation.current;
    setLoading(true); setTimeline(null); setError(null);
    setFindings([]); setFindingTotal(0); setRuns([]); setRunTotal(0);
    try {
      const [allSets, sourceRuns, evidenceRows, profileRows] = await Promise.all([authenticationApi.sets(invId), eventApi.runs(invId, sourceOffset), api.listEvidence(invId), eventApi.profiles(invId)]);
      const current = allSets.some(s => s.id === setId) ? setId : 0;
      const [executions, results, events] = current ? await Promise.all([
        authenticationApi.runs(invId, current, runOffset), authenticationApi.findings(invId, current, findingOffset, runId || undefined),
        authenticationApi.timeline(invId, current, filters, offset),
      ]) : [{ items: [], total: 0 }, { items: [], total: 0 }, null];
      if (request !== generation.current) return;
      setSets(allSets); setSources(sourceRuns); setEvidence(evidenceRows); setProfiles(profileRows); setRuns(executions.items); setRunTotal(executions.total);
      setFindings(results.items); setFindingTotal(results.total); setTimeline(events);
    } catch (err) { if (request === generation.current) setError(actionErrorMessage(err, 'Could not load the authentication workbench.')); }
    finally { if (request === generation.current) setLoading(false); }
  }, [invId, setId, sourceOffset, runOffset, findingOffset, runId, filters, offset]);
  useEffect(() => { void load(); return () => { generation.current++; }; }, [load, refresh]);

  async function act(work: () => Promise<void>) {
    setBusy(true); setError(null); setNotice('');
    try { await work(); setRefresh(n => n + 1); }
    catch (err) { setError(actionErrorMessage(err, 'The action could not complete. Inspect history before retrying.')); }
    finally { setBusy(false); }
  }
  function selectSet(value: number) {
    historyGeneration.current++; setSetId(value); setRunId(0); setRunOffset(0); setFindingOffset(0);
    setOffset(0); setFilters(emptyFilters); setDraft(emptyFilters); setDetail(null); setContextFinding(null); setEvent(null);
  }
  function pivot(values: Partial<typeof emptyFilters>) {
    const next = { ...filters, ...values, finding_id: '' };
    setFilters(next); setDraft(next); setOffset(0);
  }
  async function showFinding(finding: Finding) {
    const request = ++historyGeneration.current;
    setDetail(finding); setContextFinding(finding); setNote(finding.review_note ?? ''); setHistory([]); setNotes([]);
    try {
      const [result, annotations] = await Promise.all([authenticationApi.history(invId, finding.id), api.listNotes(invId, finding.id)]);
      if (request === historyGeneration.current) { setHistory(result); setNotes(annotations); }
    } catch (err) { if (request === historyGeneration.current) setError(actionErrorMessage(err, 'Could not load review history.')); }
  }

  return <div className="space-y-6">
    <header><h2 className="text-xl font-semibold">Authentication investigation</h2><p className="text-sm text-ink2">Select source interpretations, evaluate observable patterns, review support, and explore activity.</p>
      <Link className="text-sm underline" to={`/investigations/${invId}/events`}>Ingest logs and configure source profiles</Link></header>
    {error && <ErrorState body={error} onRetry={() => setRefresh(n => n + 1)} />}
    {notice && <p role="status" className="rounded border border-line p-3 text-sm">{notice}</p>}
    <section className="space-y-3 rounded-lg border border-line p-4" aria-label="Event selection">
      <h3 className="font-semibold">1. Select explicit event inputs</h3>
      <Field label="Saved event set" htmlFor="auth-set"><Select id="auth-set" disabled={busy} value={setId || ''} onChange={e => selectSet(Number(e.target.value))}><option value="">Choose an event set</option>{sets.map(s => <option key={s.id} value={s.id}>{s.name} · {s.semantic_key.slice(0, 10)}</option>)}</Select></Field>
      {canProduce && <details><summary className="cursor-pointer text-sm">Create a selection from ingestion runs</summary>
        <p className="mt-2 text-xs text-ink2">Choose one interpretation per source. Identical reingestions and copied observations do not add independent activity. Up to 50 runs and 10000 events.</p>
        <div className="my-3 space-y-2">{sources?.items.map(r => <label key={r.id} className="flex items-start gap-2 text-sm">
          <input type="checkbox" disabled={!['completed', 'partial'].includes(r.status) || busy} checked={selectedRuns.includes(r.id)} onChange={e => setSelectedRuns(old => e.target.checked ? [...old, r.id] : old.filter(id => id !== r.id))} />
          Run {r.id} · {evidence.find(e => e.id === r.evidence_id)?.evidence_number ?? `evidence #${r.evidence_id}`} {evidence.find(e => e.id === r.evidence_id)?.title} · {profiles.find(p => p.id === r.profile_id)?.name ?? `profile #${r.profile_id}`} · {r.status} · {r.coverage.recognized ?? 0} recognized{r.status === 'partial' ? ' (incomplete coverage)' : ''}
        </label>)}</div>
        {sources && sources.total > 25 && <Pagination offset={sourceOffset} total={sources.total} size={25} change={setSourceOffset} label="Source runs" />}
        <p className="text-xs text-ink2">{selectedRuns.length} runs selected across pages</p>
        <Field label="Selection name" htmlFor="auth-name"><Input id="auth-name" value={name} maxLength={100} onChange={e => setName(e.target.value)} /></Field>
        <Button disabled={busy || !selectedRuns.length || selectedRuns.length > 50 || !name.trim()} onClick={() => void act(async () => { const item = await authenticationApi.createSet(invId, name, selectedRuns); selectSet(item.id); setSelectedRuns([]); setNotice('Immutable event set saved. Review coverage before detection.'); })}>Save event set</Button>
      </details>}
      {selected && <><div className="grid gap-3 text-sm sm:grid-cols-3"><p>{selected.coverage.included_events} included events / {selected.coverage.selected_events} selected occurrences</p><p>{selected.coverage.sources.length} source interpretations</p><p>{selected.coverage.duplicate_source_occurrences_excluded} copied occurrences excluded</p></div>
        <p className="text-sm">{selected.coverage.authentication_events ?? 'Not recorded'} authentication events · {selected.coverage.evidence_count ?? 'Not recorded'} evidence sources</p>
        <p className="text-xs">Timestamp certainty: {JSON.stringify(selected.coverage.timestamp_certainty_counts ?? {})}</p>
        <p className="break-all font-mono text-xs">Input identity: {selected.semantic_key}</p>
        {selected.coverage.partial && <p role="alert" className="text-sm font-medium">Partial source coverage. Missing or unsupported activity must not be interpreted as absent activity.</p>}
        {selected.coverage.warnings.map(w => <p key={w} className="text-xs text-ink2">{w}</p>)}
        <details><summary className="text-sm">Source coverage and interpretation provenance</summary><pre className="overflow-auto text-xs">{JSON.stringify(selected.coverage.sources, null, 2)}</pre></details>
      </>}
    </section>
    {!setId && !loading && <EmptyState title="Choose investigation inputs" body="Select saved inputs or create a set from verified ingestions. No implicit all-events analysis is performed." />}
    {!!setId && <>
      <section className="space-y-3 rounded-lg border border-line p-4" aria-label="Detection execution">
        <h3 className="font-semibold">2. Run deterministic detections</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Window in seconds" htmlFor="auth-window"><Input id="auth-window" type="number" min={10} max={86400} value={windowSeconds} onChange={e => setWindowSeconds(Number(e.target.value))} /></Field>
          <Field label="Minimum failures" htmlFor="auth-failures"><Input id="auth-failures" type="number" min={2} max={1000} value={minFailures} onChange={e => setMinFailures(Number(e.target.value))} /></Field>
          <Field label="Spray distinct accounts" htmlFor="auth-accounts"><Input id="auth-accounts" type="number" min={2} max={1000} value={minAccounts} onChange={e => setMinAccounts(Number(e.target.value))} /></Field>
        </div>
        <label className="flex gap-2 text-sm"><input type="checkbox" checked={allowAssumed} onChange={e => setAllowAssumed(e.target.checked)} />Allow explicit profile-based time assumptions (shown in results)</label>
        <details><summary className="cursor-pointer text-sm">Advanced thresholds and processing limits</summary>
          <Field label="Repeated-failure grouping" htmlFor="auth-group"><Select id="auth-group" value={grouping} onChange={e => setGrouping(e.target.value)}><option value="account_host">Exact account and host</option><option value="account_host_source">Exact account, host and source IP</option><option value="host">Host and provider</option></Select></Field>
          <div className="grid gap-3 sm:grid-cols-3">{(Object.keys(advanced) as (keyof typeof advanced)[]).map(key => <Field key={key} label={key.replaceAll('_', ' ')} htmlFor={`auth-param-${key}`}><Input id={`auth-param-${key}`} type="number" step={key === 'burst_min_failure_fraction' ? '0.1' : '1'} value={advanced[key]} onChange={e => setAdvanced({ ...advanced, [key]: Number(e.target.value) })} /></Field>)}</div>
          <p className="text-xs text-ink2">The API validates all thresholds. Rule parameters and defaults are preserved with every run. Result limit is per family, maximum 200.</p>
        </details>
        <p className="text-xs text-ink2">Five versioned rules: repeated failures, spraying, success after failures, explicit lockouts and mixed-outcome bursts. Severity means review priority. Unknown-time events remain excluded from temporal detections.</p>
        <Button disabled={!canProduce || busy || loading || windowSeconds < 10 || windowSeconds > 86400 || minFailures < 2 || minAccounts < 2} onClick={() => void act(async () => {
          const result = await authenticationApi.execute(invId, setId, { ...advanced, grouping, window_seconds: windowSeconds, min_failures: minFailures, min_occurrences: minFailures, spray_min_accounts: minAccounts, allow_assumed_time: allowAssumed });
          setRunId(result.id); setFindingOffset(0); setRunOffset(0); setNotice(`Detection run ${result.id}: ${result.status}${result.error ? `. ${result.error}` : ''}`);
        })}>{busy ? 'Working...' : 'Run detections'}</Button>
        <Field label="Detection run" htmlFor="auth-run"><Select id="auth-run" value={runId || ''} onChange={e => { setRunId(Number(e.target.value)); setFindingOffset(0); }}><option value="">All historical runs for selected set</option>{runs.map(r => <option key={r.id} value={r.id}>Run {r.id} · {r.status} · engine {r.engine_version}</option>)}</Select></Field>
        {runTotal > 25 && <Pagination offset={runOffset} total={runTotal} size={25} change={setRunOffset} label="Detection runs" />}
        {activeRun && <><p className="text-sm">Status: {activeRun.status}. {activeRun.error}</p>
          {activeRun.status === 'running' && canProduce && <Button disabled={busy} onClick={() => void act(async () => { await authenticationApi.recover(invId, activeRun.id); setNotice('Interrupted run recovered. Retry detection explicitly.'); })}>Recover interrupted run</Button>}
          <details open><summary className="text-sm">Evaluation and omission accounting</summary><pre className="overflow-auto text-xs">{JSON.stringify(activeRun.coverage, null, 2)}</pre></details>
          <details><summary className="text-sm">Exact rule parameters</summary><pre className="overflow-auto text-xs">{JSON.stringify(activeRun.configuration, null, 2)}</pre></details>
        </>}
      </section>
      <section className="space-y-3" aria-label="Detection results"><h3 className="font-semibold">3. Review patterns ({findingTotal})</h3>
        {loading ? <p role="status">Loading investigation...</p> : !findings.length ? <EmptyState title="No results in this view" body="Check execution status, eligible events, coverage and omitted counts before drawing conclusions." /> : findings.map(f => <button key={f.id} onClick={() => void showFinding(f)} className="block w-full rounded-lg border border-line p-4 text-left hover:bg-hover">
          <span className="font-medium">{f.title}</span><span className="ml-3 text-xs">{f.severity} · {f.status} · {f.rule_id}-v{f.rule_version}</span>
          <p className="mt-1 text-sm text-ink2">{f.summary}</p><p className="text-xs">{f.support_snapshot?.event_keys?.length ?? 0} supporting events · {f.support_current ? 'Current support' : 'Historical or unavailable support'}</p>
        </button>)}
        {findingTotal > 50 && <Pagination offset={findingOffset} total={findingTotal} size={50} change={setFindingOffset} label="Findings" />}
        <Button disabled={!canReview || busy} onClick={() => void act(async () => { const report = await api.generateReport(invId, setId); setNotice(`Immutable report ${report.report_number} generated for this event set. Only accepted findings with current support enter conclusions.`); })}>Generate reviewed report</Button>{' '}<Link className="text-sm underline" to={`/investigations/${invId}/reports`}>View reports</Link>
      </section>
      <section className="space-y-3 rounded-lg border border-line p-4" aria-label="Incident timeline">
        <h3 className="font-semibold">4. Explore activity and pivot</h3>
        <p className="text-xs text-ink2">Entity filters preserve exact values. Same-name accounts on different hosts/domains are separate. Shared IP does not prove a shared actor. Equal timestamps do not establish causal order.</p>
        {filters.finding_id && <p className="text-sm">Detection context: finding #{filters.finding_id}. Showing its support only. <button className="underline" onClick={() => pivot({})}>Expand to related activity</button></p>}
        {contextFinding && <Button onClick={() => void showFinding(contextFinding)}>Return to finding #{contextFinding.id}</Button>}
        {filters.domain_missing && <p className="text-xs">Account pivot scope: missing domain, provider {filters.provider}, host {filters.host}. Clear filters to leave this scope.</p>}
        <form onSubmit={e => { e.preventDefault(); setFilters(draft); setOffset(0); }} className="grid gap-3 sm:grid-cols-3">
          <Field label="Time interpretation" htmlFor="auth-time"><Select id="auth-time" value={draft.lane} onChange={e => setDraft({ ...draft, lane: e.target.value, start: '', end: '' })}><option value="utc">Source-declared UTC projections</option><option value="assumed">Profile-assumed projections</option><option value="uncertain">Unknown / ambiguous time</option></Select></Field>
          {(['username', 'account_domain', 'host', 'source_ip', 'event_type'] as const).map(key => <Field key={key} label={key.replaceAll('_', ' ')} htmlFor={`auth-filter-${key}`}><Input id={`auth-filter-${key}`} value={draft[key]} onChange={e => setDraft({ ...draft, [key]: e.target.value })} /></Field>)}
          <Field label="Outcome" htmlFor="auth-outcome"><Select id="auth-outcome" value={draft.outcome} onChange={e => setDraft({ ...draft, outcome: e.target.value })}><option value="">All outcomes</option><option value="failure">Failure</option><option value="success">Success</option><option value="unknown">Unknown</option></Select></Field>
          {(['start', 'end'] as const).map(key => <Field key={key} label={`${key} (ISO timestamp with offset)`} htmlFor={`auth-filter-${key}`}><Input id={`auth-filter-${key}`} disabled={draft.lane === 'uncertain'} value={draft[key]} placeholder="2026-11-05T12:00:00Z" onChange={e => setDraft({ ...draft, [key]: e.target.value })} /></Field>)}
          <Button type="submit" disabled={loading}>Apply timeline filters</Button><Button type="button" onClick={() => { setDraft(emptyFilters); setFilters(emptyFilters); setOffset(0); }}>Clear filters and return to event set</Button>
        </form>
        {timeline && <><p className="text-sm">{timeline.total} events in this lane. {timeline.ordering}</p>
          <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th>Source time / certainty</th><th>Activity</th><th>Account</th><th>Source IP</th><th>Host / source</th></tr></thead><tbody>{timeline.items.map(e => <tr key={e.semantic_key} className="border-t border-line">
            <td className="p-2"><button className="text-left underline" onClick={() => setEvent(e)}>{e.original_timestamp ?? 'Timestamp missing'}</button><p className="text-xs text-ink2">{e.time_semantics.certainty} · {e.timestamp_utc ?? 'No UTC projection'}</p></td>
            <td className="p-2">{e.provider} · {e.event_type}<p>{e.outcome}</p></td>
            <td className="p-2"><button disabled={!e.username || !e.hostname} className="underline disabled:no-underline" onClick={() => pivot({ username: e.username ?? '', account_domain: e.account_domain ?? '', domain_missing: e.account_domain ? '' : 'true', provider: e.account_domain ? '' : e.provider, host: e.hostname ?? '' })}>{e.account_domain ? `${e.account_domain}\\` : ''}{e.username ?? 'Unknown'}</button></td>
            <td className="p-2"><button disabled={!e.source_ip} className="underline" onClick={() => pivot({ source_ip: e.source_ip ?? '' })}>{e.source_ip ?? 'Unknown'}</button></td>
            <td className="p-2"><button className="underline" disabled={!e.hostname} onClick={() => pivot({ host: e.hostname ?? '' })}>{e.hostname ?? 'Unknown host'}</button><p><Link className="underline text-xs" to={`/investigations/${invId}/evidence/${e.evidence_id}`}>Evidence #{e.evidence_id}</Link></p><button className="text-xs underline" onClick={() => setEvent(e)}>Inspect source locator</button></td>
          </tr>)}</tbody></table></div>
          {!timeline.items.length && <p className="text-sm text-ink2">No events match this lane and filters. Inspect other time lanes before concluding activity is absent.</p>}
          <Pagination offset={offset} total={timeline.total} size={50} change={setOffset} label="Timeline" />
        </>}
      </section>
    </>}
    <Drawer open={!!detail} title={detail?.title ?? 'Detection detail'} onClose={closeFinding}>
      {detail && <div className="space-y-4 text-sm"><p>{detail.summary}</p><p>{detail.severity} · {detail.status} · {detail.rule_id}-v{detail.rule_version}</p>
        {!detail.support_current && <p role="alert">Historical or unavailable support. This finding cannot enter current accepted report conclusions.</p>}
        <p>{detail.support_snapshot?.detection?.severity_rationale}</p>
        <ul className="list-disc pl-5">{detail.support_snapshot?.detection?.limitations.map(w => <li key={w}>{w}</li>)}</ul>
        <p>{detail.support_snapshot?.event_keys?.length ?? 0} exact support identities retained.</p>
        <pre className="overflow-auto text-xs">{JSON.stringify({ input: detail.support_snapshot?.event_set_key, entities: detail.support_snapshot?.detection?.entities, start: detail.support_snapshot?.detection?.time_start, end: detail.support_snapshot?.detection?.time_end, parameters: detail.support_snapshot?.detection?.configuration }, null, 2)}</pre>
        <Button onClick={() => { const next = { ...emptyFilters, finding_id: String(detail.id) }; setFilters(next); setDraft(next); setOffset(0); closeFinding(); }}>Explore supporting events in timeline</Button>
        <p className="text-xs text-ink2">Support may include profile-assumed timestamps. Inspect that lane when applicable.</p>
        <Field label="Analyst review note" htmlFor="auth-note"><Textarea id="auth-note" value={note} maxLength={1000} onChange={e => setNote(e.target.value)} /></Field>
        {canReview && <div className="flex gap-2">{(['accepted', 'rejected'] as const).map(status => <Button key={status} disabled={busy || (status === 'accepted' && !detail.support_current)} onClick={() => { const request = historyGeneration.current; void act(async () => { const saved = await api.reviewFinding(invId, detail.id, status, note); if (request === historyGeneration.current) await showFinding(saved); setNotice(`Finding ${detail.id} ${status}.`); }); }}>{status === 'accepted' ? 'Accept finding' : 'Reject finding'}</Button>)}</div>}
        <Button disabled={!canProduce || busy || !note.trim()} onClick={() => void act(async () => { await api.createNote(invId, note, detail.id); setNotes(await api.listNotes(invId, detail.id)); setNotice('Analyst annotation saved through the shared investigation notes workflow.'); })}>Save annotation</Button>
        <h4 className="font-semibold">Investigator annotations</h4>{notes.map(n => <p key={n.id} className="whitespace-pre-wrap">{n.body}</p>)}
        <h4 className="font-semibold">Supporting event preview (up to 20)</h4>
        <ol className="space-y-2">{detail.support_snapshot?.source_events?.slice(0, 20).map(e => <li key={e.semantic_key} className="rounded border border-line p-2">
          <p>{e.original_timestamp ?? 'Unknown time'} · {e.time_semantics.certainty} · {e.username ?? 'Unknown account'} · {e.hostname ?? 'Unknown host'} · {e.source_ip ?? 'Unknown source'}</p>
          <Link className="underline" to={`/investigations/${invId}/evidence/${e.evidence_id}`}>Evidence #{e.evidence_id}</Link><p className="break-all font-mono text-xs">{JSON.stringify(e.locator)}</p>
        </li>)}</ol>
        <p className="text-xs text-ink2">The timeline retrieves complete retained support; this preview is bounded.</p>
        <h4 className="font-semibold">Review history (latest 100)</h4>{history.map((h, i) => <pre key={i} className="overflow-auto text-xs">{JSON.stringify(h, null, 2)}</pre>)}
      </div>}
    </Drawer>
    <Drawer open={!!event} title="Supporting event provenance" onClose={closeEvent}>{event && <EventDetail event={event} invId={invId} />}</Drawer>
  </div>;
}

function Pagination({ offset, total, size, change, label }: { offset: number; total: number; size: number; change: (value: number) => void; label: string }) {
  return <nav aria-label={`${label} pagination`} className="flex items-center gap-3 text-sm"><Button disabled={offset === 0} onClick={() => change(Math.max(0, offset - size))}>Previous {label.toLowerCase()}</Button><span>{total ? offset + 1 : 0}-{Math.min(offset + size, total)} of {total}</span><Button disabled={offset + size >= total} onClick={() => change(offset + size)}>Next {label.toLowerCase()}</Button></nav>;
}
