import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import EvidenceDetailPage from './EvidenceDetailPage';
let role = 'forensic_analyst'; let status = 'open';
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ user: { id: 2, role } }) }));
vi.mock('../components/Toast', () => ({ useToast: () => ({ notify: vi.fn() }) }));
vi.mock('../api/client', () => ({ api: {
  getInvestigation: vi.fn(async () => ({ id: 1, title: 'Synthetic', status, created_by: { id: 1 }, lead_investigator: { id: 1 } })),
  getEvidence: vi.fn(async () => ({ id: 1, title: 'Synthetic log', evidence_number: 'E-001', evidence_type: 'log', original_filename: 'auth.log', file_size: 100, sha256: 'a'.repeat(64), registration_status: 'ready', integrity_status: 'verified', registered_by: { id: 1, username: 'synthetic', full_name: 'Invented User' } })),
  listVerifications: vi.fn(async () => []), listCustody: vi.fn(async () => []), evidenceTimeline: vi.fn(async () => []),
} }));
beforeEach(() => { role = 'forensic_analyst'; status = 'open'; });
for (const [assigned, state, disabled] of [['forensic_analyst', 'open', true], ['evidence_custodian', 'open', false], ['evidence_custodian', 'archived', true], ['admin', 'archived', false]] as const) {
  it(`shows correct verification permission for ${assigned} in ${state}`, async () => {
    role = assigned; status = state;
    render(<MemoryRouter initialEntries={['/investigations/1/evidence/1']}><Routes><Route path="/investigations/:id/evidence/:eid" element={<EvidenceDetailPage />} /></Routes></MemoryRouter>);
    const button = await screen.findByRole('button', { name: 'Verify integrity' });
    if (disabled) expect(button).toBeDisabled(); else expect(button).toBeEnabled();
  });
}
