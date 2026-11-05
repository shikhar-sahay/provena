import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AuthenticationWorkbench } from './AuthenticationPage';
import { api, authenticationApi, eventApi } from '../api/client';
import type { Finding, SecurityEvent, InvestigationEventSet, AuthenticationRun, Report } from '../api/client';

vi.mock('../api/client', async original => ({ ...(await original<typeof import('../api/client')>()),
  eventApi: { runs: vi.fn(), profiles: vi.fn() },
  authenticationApi: { sets: vi.fn(), createSet: vi.fn(), execute: vi.fn(), runs: vi.fn(), findings: vi.fn(), timeline: vi.fn(), history: vi.fn(), recover: vi.fn() },
  api: { reviewFinding: vi.fn(), createNote: vi.fn(), listNotes: vi.fn(), generateReport: vi.fn(), listEvidence: vi.fn() },
}));

const selection: InvestigationEventSet = { id: 1, name: 'Explicit lab inputs', semantic_key: 'a'.repeat(64), selected_runs: [3],
  coverage: { selected_events: 12, included_events: 6, duplicate_source_occurrences_excluded: 6, partial: true,
    warnings: ['Source-clock synchronization is unverified.'], sources: [{ input_sha256: 'b'.repeat(64), profile_key: 'c'.repeat(64), status: 'partial', coverage: { recognized: 6, unrecognized: 1 } }] } };
const finding: Finding = { id: 4, investigation_id: 1, rule_id: 'auth.repeated_failures', rule_version: '1',
  title: 'Repeated failures candidate', summary: 'Five observed failures meet the threshold.', severity: 'medium', confidence: 0,
  factors: [], evidence_ids: [2], artifact_ids: [], correlation_ids: [], recommendations: [], status: 'pending_review',
  reviewer_username: null, reviewed_at: null, review_note: null, created_at: '', updated_at: '', support_current: true,
  support_snapshot: { kind: 'authentication_detection', event_set_id: 1, event_set_key: selection.semantic_key, event_keys: ['event-key'],
    detection: { rule_id: 'auth.repeated_failures', rule_version: '1', count: 5, entities: { group: [null, 'mira', 'lab', 'sshd'] },
      severity_rationale: 'Threshold-based priority, not probability.', limitations: ['Shared IP does not identify an actor.'], configuration: { min_failures: 5 },
      event_keys: ['event-key'], time_start: '2026-11-05T12:00:00Z', time_end: '2026-11-05T12:00:12Z' } } };
const event: SecurityEvent = { id: 1, semantic_key: 'event-key', evidence_id: 2, evidence_number: 'E-002', first_run_id: 3, profile_id: 4,
  input_sha256: 'b'.repeat(64), record_fingerprint: 'c'.repeat(64), provider: 'sshd', category: 'authentication', event_type: 'logon',
  outcome: 'failure', event_id: null, username: 'mira', account_domain: null, hostname: 'lab', source_ip: '192.0.2.1',
  destination_ip: null, source_port: 22, destination_port: null, original_timestamp: 'Nov 5 12:00:00', timestamp_utc: null,
  time_semantics: { certainty: 'unknown', precision: 'second', assumptions: [], warnings: [] }, attributes: {}, warnings: [],
  locator: { line: 1 }, profile_snapshot: {}, adapter_version: '1.1', normalization_version: '1.tz2026.6', coverage_status: 'partial', support_verified: true };
const run: AuthenticationRun = { id: 7, event_set_id: 1, status: 'completed', engine_version: '1', error: null, configuration: { min_failures: 5 },
  coverage: { evaluated: 6, eligible: 5, excluded: { unsupported_time: 1 }, result_count: 1, rules: { repeated_failures: { candidates: 2, returned: 1, omitted: 1 } } } };

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(authenticationApi.sets).mockResolvedValue([selection]);
  vi.mocked(api.listEvidence).mockResolvedValue([]);
  vi.mocked(eventApi.profiles).mockResolvedValue([]);
  vi.mocked(eventApi.runs).mockResolvedValue({ items: [{ id: 3, evidence_id: 2, profile_id: 4, status: 'partial', input_sha256: event.input_sha256, verification_id: 1, coverage: { recognized: 6 }, error: null, created_at: '' }], total: 1, limit: 25, offset: 0 });
  vi.mocked(authenticationApi.runs).mockResolvedValue({ items: [run], total: 1 });
  vi.mocked(authenticationApi.findings).mockResolvedValue({ items: [finding], total: 1 });
  vi.mocked(authenticationApi.timeline).mockResolvedValue({ items: [event], total: 51, ordering: 'Stable display ordering is not causal order.', lane: 'utc', coverage: selection.coverage });
  vi.mocked(authenticationApi.createSet).mockResolvedValue(selection);
  vi.mocked(authenticationApi.execute).mockResolvedValue(run);
  vi.mocked(authenticationApi.history).mockResolvedValue([]);
  vi.mocked(api.listNotes).mockResolvedValue([]);
  vi.mocked(api.reviewFinding).mockResolvedValue({ ...finding, status: 'accepted' });
});

function renderWorkbench(canProduce = true, canReview = true) {
  return render(<MemoryRouter><AuthenticationWorkbench invId={1} canProduce={canProduce} canReview={canReview} /></MemoryRouter>);
}
async function choose() {
  await screen.findByRole('option', { name: /Explicit lab inputs/ });
  await userEvent.selectOptions(screen.getByLabelText('Saved event set'), '1');
  await screen.findByText(finding.title);
}

it('requires explicit selection and displays incomplete source coverage', async () => {
  renderWorkbench();
  await screen.findByText('Choose investigation inputs');
  expect(authenticationApi.timeline).not.toHaveBeenCalled();
  await choose();
  expect(screen.getByText(/Partial source coverage/)).toBeInTheDocument();
  expect(screen.getByText('6 copied occurrences excluded')).toBeInTheDocument();
  expect(screen.getByText(selection.semantic_key, { exact: false })).toBeInTheDocument();
});

it('creates immutable selections and persists validated detection parameters', async () => {
  const user = userEvent.setup();
  renderWorkbench();
  await screen.findByText('Create a selection from ingestion runs');
  await user.click(screen.getByText('Create a selection from ingestion runs'));
  await user.click(screen.getByRole('checkbox', { name: /Run 3/ }));
  await user.click(screen.getByRole('button', { name: 'Save event set' }));
  await screen.findByText(finding.title);
  expect(authenticationApi.createSet).toHaveBeenCalledWith(1, 'Authentication investigation', [3]);
  await user.click(screen.getByRole('button', { name: 'Run detections' }));
  await waitFor(() => expect(authenticationApi.execute).toHaveBeenCalledWith(1, 1, expect.objectContaining({ min_failures: 5, allow_assumed_time: false })));
  expect(await screen.findByText(/unsupported_time/)).toBeInTheDocument();
  expect(screen.getByText(/"omitted": 1/)).toBeInTheDocument();
});

it('preserves exact account scope, changes uncertainty lanes and paginates', async () => {
  const user = userEvent.setup();
  renderWorkbench(); await choose();
  await user.click(screen.getByRole('button', { name: 'mira' }));
  await waitFor(() => expect(authenticationApi.timeline).toHaveBeenLastCalledWith(1, 1, expect.objectContaining({ username: 'mira', host: 'lab', domain_missing: 'true', provider: 'sshd' }), 0));
  await user.selectOptions(screen.getByLabelText('Time interpretation'), 'uncertain');
  await user.click(screen.getByRole('button', { name: 'Apply timeline filters' }));
  await waitFor(() => expect(authenticationApi.timeline).toHaveBeenLastCalledWith(1, 1, expect.objectContaining({ lane: 'uncertain' }), 0));
  expect(screen.getByLabelText('start (ISO timestamp with offset)')).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Next timeline' }));
  await waitFor(() => expect(authenticationApi.timeline).toHaveBeenLastCalledWith(1, 1, expect.anything(), 50));
});

it('reviews through shared finding API and opens exact support in context', async () => {
  const user = userEvent.setup();
  renderWorkbench(); await choose();
  await user.click(screen.getByText(finding.title));
  await user.type(screen.getByLabelText('Analyst review note'), 'Checked synthetic sources');
  await user.click(screen.getByRole('button', { name: 'Accept finding' }));
  await waitFor(() => expect(api.reviewFinding).toHaveBeenCalledWith(1, 4, 'accepted', 'Checked synthetic sources'));
  expect(screen.queryByText('Confidence 0/100')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Explore supporting events in timeline' }));
  await waitFor(() => expect(authenticationApi.timeline).toHaveBeenLastCalledWith(1, 1, expect.objectContaining({ finding_id: '4' }), 0));
  expect(await screen.findByText(/Detection context: finding #4/)).toBeInTheDocument();
});

it('shows source locators and safe failure states', async () => {
  const user = userEvent.setup();
  renderWorkbench(); await choose();
  await user.click(screen.getByRole('button', { name: 'Inspect source locator' }));
  expect(await screen.findByRole('dialog', { name: 'Supporting event provenance' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Open source evidence/ })).toHaveAttribute('href', '/investigations/1/evidence/2');
});

it('enforces review controls and disables accepting historical support', async () => {
  const user = userEvent.setup();
  vi.mocked(authenticationApi.findings).mockResolvedValue({ items: [{ ...finding, support_current: false }], total: 1 });
  renderWorkbench(false, true); await choose();
  expect(screen.getByRole('button', { name: 'Run detections' })).toBeDisabled();
  await user.click(screen.getByText(finding.title));
  expect(screen.getByRole('button', { name: 'Accept finding' })).toBeDisabled();
  expect(screen.getByText('Historical or unavailable support. This finding cannot enter current accepted report conclusions.')).toBeInTheDocument();
});

it('shows API errors without pretending an empty result is successful', async () => {
  vi.mocked(authenticationApi.timeline).mockRejectedValue(new Error('Synthetic unavailable'));
  renderWorkbench();
  await screen.findByRole('option', { name: /Explicit lab inputs/ });
  await userEvent.selectOptions(screen.getByLabelText('Saved event set'), '1');
  expect(await screen.findByText(/Could not load the authentication workbench/)).toBeInTheDocument();
});

it('generates a report with explicit selected-set scope', async () => {
  vi.mocked(api.generateReport).mockResolvedValue({ report_number: 2 } as Report);
  renderWorkbench(); await choose();
  await userEvent.click(screen.getByRole('button', { name: 'Generate reviewed report' }));
  await waitFor(() => expect(api.generateReport).toHaveBeenCalledWith(1, 1));
  expect(await screen.findByText(/Immutable report 2 generated for this event set/)).toBeInTheDocument();
});

it('keeps omission and execution context visible when no detections are returned', async () => {
  vi.mocked(authenticationApi.findings).mockResolvedValue({ items: [], total: 0 });
  renderWorkbench();
  await screen.findByRole('option', { name: /Explicit lab inputs/ });
  await userEvent.selectOptions(screen.getByLabelText('Saved event set'), '1');
  expect(await screen.findByText('No results in this view')).toBeInTheDocument();
  expect(screen.getByText(/Check execution status, eligible events, coverage and omitted counts/)).toBeInTheDocument();
});

it('does not display old findings under a new selection when its request fails', async () => {
  vi.mocked(authenticationApi.sets).mockResolvedValue([selection, { ...selection, id: 2, name: 'Alternative selection' }]);
  const page = { items: [event], total: 1, ordering: 'UTC projection', lane: 'utc', coverage: selection.coverage };
  vi.mocked(authenticationApi.timeline).mockImplementation((_id, selected) => selected === 2 ? Promise.reject(new Error('Synthetic failed selection')) : Promise.resolve(page));
  renderWorkbench(); await choose();
  await userEvent.selectOptions(screen.getByLabelText('Saved event set'), '2');
  await screen.findByText(/Could not load the authentication workbench/);
  expect(screen.queryByText(finding.title)).not.toBeInTheDocument();
});
