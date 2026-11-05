import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExportWorkbench } from './ExportsPage';
import { api, authenticationApi, exportApi } from '../api/client';
import type { Evidence, InvestigationExport, InvestigationEventSet } from '../api/client';

vi.mock('../api/client', async original => ({ ...(await original<typeof import('../api/client')>()),
  api: { listEvidence: vi.fn(), listReports: vi.fn() }, authenticationApi: { sets: vi.fn() },
  exportApi: { list: vi.fn(), create: vi.fn(), download: vi.fn(), recover: vi.fn() },
}));
const item: InvestigationExport = { id: 4, investigation_id: 1, requested_by_id: 1, mode: 'metadata', status: 'completed',
  selection: { event_set_ids: [], report_ids: [], evidence_ids: [] }, package_sha256: 'a'.repeat(64), byte_size: 2048, error: null,
  created_at: '', manifest_summary: { files: 22, originals: 0, warnings: ['Unsigned consistency only.'] } };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.listEvidence).mockResolvedValue([{ id: 2, evidence_number: 'E-002', title: 'Synthetic authentication',
    integrity_status: 'verified', registration_status: 'ready', file_size: 100 } as Evidence]);
  vi.mocked(api.listReports).mockResolvedValue([]);
  vi.mocked(authenticationApi.sets).mockResolvedValue([{ id: 3, name: 'Explicit inputs', coverage: { included_events: 6, partial: true } } as InvestigationEventSet]);
  vi.mocked(exportApi.list).mockResolvedValue([]);
  vi.mocked(exportApi.create).mockResolvedValue(item);
});

it('defaults to metadata only and requires explicit original selection', async () => {
  const user = userEvent.setup(); render(<ExportWorkbench invId={1} canExportOriginals />);
  await screen.findByText('No exports on this page');
  await user.click(screen.getByRole('button', { name: 'Create export snapshot' }));
  expect(exportApi.create).toHaveBeenCalledWith(1, { mode: 'metadata', event_set_ids: [], report_ids: [], evidence_ids: [] }, expect.any(String));
  await user.selectOptions(screen.getByLabelText('Export mode'), 'originals');
  expect(screen.getByRole('button', { name: 'Create export snapshot' })).toBeDisabled();
  await user.click(screen.getByRole('checkbox', { name: /E-002/ }));
  await user.click(screen.getByRole('button', { name: 'Create export snapshot' }));
  expect(exportApi.create).toHaveBeenLastCalledWith(1, expect.objectContaining({ mode: 'originals', evidence_ids: [2] }), expect.any(String));
});

it('does not offer original content to a non-manager', async () => {
  render(<ExportWorkbench invId={1} canExportOriginals={false} />);
  await screen.findByText('No exports on this page');
  expect(screen.queryByRole('option', { name: /Include explicitly selected/ })).not.toBeInTheDocument();
  expect(screen.getByText(/does not prove authenticity/)).toBeInTheDocument();
});

it('retains the request key after ambiguous creation failure', async () => {
  vi.mocked(exportApi.create).mockRejectedValueOnce(new Error('Synthetic lost connection')).mockResolvedValueOnce(item);
  const user = userEvent.setup(); render(<ExportWorkbench invId={1} canExportOriginals />);
  await screen.findByText('No exports on this page');
  await user.click(screen.getByRole('button', { name: 'Create export snapshot' }));
  await screen.findByText(/Could not confirm export creation/);
  const first = vi.mocked(exportApi.create).mock.calls[0][2];
  await user.click(screen.getByRole('button', { name: 'Create export snapshot' }));
  await waitFor(() => expect(exportApi.create).toHaveBeenCalledTimes(2));
  expect(vi.mocked(exportApi.create).mock.calls[1][2]).toBe(first);
});

it('shows verified history, starts downloads and exposes safe failure states', async () => {
  vi.mocked(exportApi.list).mockResolvedValue([item, { ...item, id: 5, status: 'failed', package_sha256: null, byte_size: null, error: 'No partial package is downloadable.' }]);
  const user = userEvent.setup(); render(<ExportWorkbench invId={1} canExportOriginals />);
  await screen.findByText('Export #4 · metadata · completed');
  expect(screen.getByRole('button', { name: 'Download export #5' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Download export #4' }));
  expect(exportApi.download).toHaveBeenCalledWith(1, item);
  expect(screen.getByText(/Package SHA-256/)).toHaveTextContent(item.package_sha256!);
});
