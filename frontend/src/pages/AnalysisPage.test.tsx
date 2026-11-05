import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import AnalysisPage from './AnalysisPage';
let role = 'investigator'; let state = 'open';
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ user: { id: 2, role } }) }));
vi.mock('../components/Toast', () => ({ useToast: () => ({ notify: vi.fn() }) }));
vi.mock('../api/client', () => ({ api: {
  listAnalysisRuns: vi.fn(async () => []), analysisEligibility: vi.fn(async () => []),
  listArtifacts: vi.fn(async () => ({ total: 0, items: [] })), listCorrelations: vi.fn(async () => []),
  listFindings: vi.fn(async () => []), findingCoverage: vi.fn(async () => []),
} }));
beforeEach(() => { role = 'investigator'; state = 'open'; });
for (const [assigned, status, allowed] of [['investigator', 'open', false], ['forensic_analyst', 'open', true], ['forensic_analyst', 'archived', false], ['admin', 'archived', true]] as const) {
  it(`enforces analysis controls for assigned ${assigned} in ${status}`, async () => {
    role = assigned; state = status;
    const context = { inv: { id: 1, title: 'Synthetic', status: state, created_by: { id: 1 }, lead_investigator: { id: 1 } }, canManage: role === 'admin', archivedLocked: state === 'archived' && role !== 'admin' };
    render(<MemoryRouter initialEntries={['/investigations/1/analysis']}><Routes><Route path="/investigations/:id" element={<Outlet context={context} />}><Route path="analysis" element={<AnalysisPage />} /></Route></Routes></MemoryRouter>);
    await screen.findByRole('tab', { name: 'Overview' });
    if (allowed) expect(screen.getAllByRole('button', { name: 'Run analysis' }).length).toBeGreaterThan(0);
    else expect(screen.queryByRole('button', { name: 'Run analysis' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: 'Findings' }));
    const evaluate = await screen.findByRole('button', { name: 'Evaluate rules' });
    if (allowed) expect(evaluate).toBeEnabled(); else expect(evaluate).toBeDisabled();
  });
}
