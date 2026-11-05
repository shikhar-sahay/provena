import { afterEach, expect, it, vi } from 'vitest';
import { exportApi } from './client';
import type { InvestigationExport } from './client';

const item = { id: 2, mode: 'metadata', byte_size: 3 } as InvestigationExport;
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); localStorage.clear(); });
function response(bytes: number[]) {
  return { ok: true, body: new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(bytes)); controller.close(); } }) };
}

it('downloads a bounded archive using an authorization header and safe filename', async () => {
  vi.useFakeTimers(); localStorage.setItem('provena_token', 'synthetic-token');
  const fetcher = vi.fn().mockResolvedValue(response([1, 2, 3])); vi.stubGlobal('fetch', fetcher);
  const create = vi.fn().mockReturnValue('blob:synthetic'); const revoke = vi.fn();
  vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke });
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    expect(this.download).toBe('provena-case-1-export-2.zip');
  });
  await exportApi.download(1, item);
  expect(fetcher).toHaveBeenCalledWith('/api/investigations/1/exports/2/download', { headers: { Authorization: 'Bearer synthetic-token' } });
  expect(click).toHaveBeenCalledOnce(); expect(create).toHaveBeenCalledOnce();
  await vi.runAllTimersAsync(); expect(revoke).toHaveBeenCalledWith('blob:synthetic');
});

it('rejects oversized content before creating a browser download', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response([1, 2, 3, 4])));
  await expect(exportApi.download(1, item)).rejects.toThrow('exceeded its recorded size');
});

it('rejects an incomplete download', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response([1])));
  await expect(exportApi.download(1, item)).rejects.toThrow('incomplete');
});

it('reports authorization expiry without exposing response internals', async () => {
  const listener = vi.fn(); window.addEventListener('provena:unauthorized', listener);
  try {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401 }));
    await expect(exportApi.download(1, item)).rejects.toThrow('access was denied');
    expect(listener).toHaveBeenCalledOnce();
  } finally { window.removeEventListener('provena:unauthorized', listener); }
});
