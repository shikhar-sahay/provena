import { test as base, expect, type Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';

const api = process.env.M6_API_URL!;
const password = 'Synthetic-local-only-2468';
const test = base.extend({ page: async ({ page }, runFixture) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    expect([process.env.M6_WEB_URL, api]).toContain(url.origin);
    await route.continue();
  });
  await runFixture(page);
  expect(errors).toEqual([]);
} });

async function request(page: Page, path: string, method = 'GET', body?: unknown) {
  return page.evaluate(async ({ url, method, body }) => {
    const response = await fetch(url, { method, headers: { Authorization: `Bearer ${localStorage.getItem('provena_token')}`, 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
    return { status: response.status, body: await response.json() };
  }, { url: api + '/api' + path, method, body });
}
async function onboard(page: Page) {
  const name = `m6_${randomUUID().slice(0, 8)}`;
  await page.goto('/register');
  await page.getByLabel('Full name', { exact: true }).fill('Synthetic Investigator');
  await page.getByLabel('Username', { exact: true }).fill(name);
  await page.getByLabel('Email', { exact: true }).fill(`${name}@example.test`);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page).toHaveURL(/onboarding/);
  await page.getByLabel('Workspace name', { exact: true }).fill(`Lab ${name}`);
  await page.locator('form button[type="submit"]').click();
  await expect(page).not.toHaveURL(/onboarding/);
  return name;
}
async function createCase(page: Page, title = 'Synthetic authentication investigation') {
  await page.goto('/investigations');
  await page.getByRole('button', { name: 'New investigation', exact: true }).first().click();
  const dialog = page.getByRole('dialog', { name: 'New investigation' });
  await dialog.getByLabel('Title', { exact: true }).fill(title);
  await dialog.getByRole('button', { name: 'Create investigation', exact: true }).click();
  await expect(page).toHaveURL(/\/investigations\/\d+$/);
  return Number(new URL(page.url()).pathname.split('/').at(-1));
}
async function upload(page: Page, id: number, filename: string, content?: Buffer) {
  await page.goto(`/investigations/${id}/evidence/register`);
  await page.getByLabel('Evidence file', { exact: true }).setInputFiles(content ? { name: filename, mimeType: 'text/plain', buffer: content } : resolve('../sample-data/m4-authentication', filename));
  await page.getByLabel('Title', { exact: true }).fill(filename);
  const uploaded = page.waitForResponse(r => r.url().endsWith(`/investigations/${id}/evidence`) && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Register evidence', exact: true }).click();
  const item = await (await uploaded).json();
  expect(item.registration_status).toBe('ready');
  await expect(page).toHaveURL(new RegExp(`/evidence/${item.id}$`));
  const verified = page.waitForResponse(r => r.url().endsWith(`/evidence/${item.id}/verify`));
  await page.getByRole('button', { name: 'Verify integrity', exact: true }).click();
  expect((await (await verified).json()).result).toBe('verified');
  return item;
}
async function ingest(page: Page, id: number, item: { id: number }, adapter: string, label: string) {
  await page.goto(`/investigations/${id}/events`);
  await page.getByRole('button', { name: 'Configure source profile' }).click();
  await page.getByLabel('Profile name', { exact: true }).fill(label);
  await page.getByLabel('Adapter', { exact: true }).selectOption(adapter);
  const saved = page.waitForResponse(r => r.url().endsWith('/events/profiles') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save source profile' }).click();
  const profile = await (await saved).json();
  await page.getByLabel('Evidence to ingest', { exact: true }).selectOption(String(item.id));
  await page.getByLabel('Source interpretation profile', { exact: true }).selectOption(String(profile.id));
  const ingested = page.waitForResponse(r => r.url().endsWith('/events/runs') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Ingest verified evidence' }).click();
  const run = await (await ingested).json();
  expect(['partial', 'completed']).toContain(run.status);
  return { run, profile };
}

test('complete investigation, stable review, timeline, report and verified browser exports', async ({ page }, info) => {
  test.setTimeout(240_000);
  await onboard(page); const id = await createCase(page);
  const sources = [];
  for (const [file, adapter] of [['linux-auth.txt', 'linux_auth'], ['windows-security.jsonl', 'windows_security'], ['sysmon-context.jsonl', 'sysmon']]) {
    const item = await upload(page, id, file);
    const interpreted = await ingest(page, id, item, adapter, adapter);
    sources.push({ item, ...interpreted });
  }
  await expect(page.getByText(/51 events; showing 1-50/)).toBeVisible();
  await page.getByRole('button', { name: 'Next events', exact: true }).click();
  await expect(page.getByText(/51 events; showing 51-51/)).toBeVisible();
  await page.getByLabel('Outcome', { exact: true }).selectOption('failure');
  await page.getByRole('button', { name: 'Apply event filters' }).click();
  await expect(page.getByRole('button', { name: 'Next events', exact: true })).toBeDisabled();
  const original = (await request(page, `/investigations/${id}/events?limit=200`)).body;
  expect(original.total).toBe(51);
  await page.goto(`/investigations/${id}/authentication`);
  await page.getByText('Create a selection from ingestion runs', { exact: true }).click();
  const selection = page.getByRole('region', { name: 'Event selection' });
  await expect(selection.getByRole('checkbox')).toHaveCount(3);
  for (const checkbox of await selection.getByRole('checkbox').all()) await checkbox.check();
  await page.getByLabel('Selection name', { exact: true }).fill('Verified browser selection');
  const selected = page.waitForResponse(r => r.url().endsWith('/authentication/sets') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save event set' }).click();
  const set = await (await selected).json(); expect(set.coverage.included_events).toBe(51);
  await page.getByRole('button', { name: 'Run detections', exact: true }).click();
  await expect(page.getByRole('heading', { name: '3. Review patterns (5)' })).toBeVisible();
  const results = page.getByRole('region', { name: 'Detection results' });
  const spray = results.getByRole('button').filter({ hasText: /password.*spray/i });
  await spray.click();
  const detail = page.getByRole('dialog');
  await detail.getByLabel('Analyst review note').fill('Synthetic source records inspected in Chromium.');
  await detail.getByRole('button', { name: 'Accept finding', exact: true }).click();
  await expect(detail.getByText(/accepted/).first()).toBeVisible();
  await detail.getByRole('button', { name: 'Save annotation', exact: true }).click();
  await expect(detail.getByText('Synthetic source records inspected in Chromium.', { exact: true }).first()).toBeVisible();
  await detail.getByRole('button', { name: 'Explore supporting events in timeline' }).click();
  const timeline = page.getByRole('region', { name: 'Incident timeline' });
  await expect(timeline.getByText(/5 events in this lane/)).toBeVisible();
  await timeline.getByRole('button', { name: '192.0.2.20', exact: true }).first().click();
  await expect(timeline.getByText(/6 events in this lane/)).toBeVisible();
  const accountButton = timeline.locator('tbody tr').first().getByRole('cell').nth(2).getByRole('button');
  const account = await accountButton.innerText(); await accountButton.click();
  await expect(page.getByLabel('username', { exact: true })).toHaveValue(account);
  const hostButton = timeline.locator('tbody tr').first().getByRole('cell').nth(4).getByRole('button').first();
  const host = await hostButton.innerText(); await hostButton.click();
  await expect(page.getByLabel('host', { exact: true })).toHaveValue(host);
  await timeline.getByRole('button', { name: 'Inspect source locator', exact: true }).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByLabel('Time interpretation', { exact: true }).selectOption('uncertain');
  await page.getByRole('button', { name: 'Clear filters and return to event set' }).click();
  await page.getByLabel('Time interpretation', { exact: true }).selectOption('uncertain');
  await page.getByRole('button', { name: 'Apply timeline filters' }).click();
  await expect(timeline.getByText(/6 events in this lane/)).toBeVisible();
  await results.getByRole('button').filter({ hasText: /burst/i }).click();
  await page.getByRole('dialog').getByLabel('Analyst review note').fill('Synthetic benign service burst, rejected for this exercise.');
  await page.getByRole('button', { name: 'Reject finding', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: /Finding \d+ rejected/ })).toBeVisible();
  await page.keyboard.press('Escape');
  const before = (await request(page, `/investigations/${id}/authentication/findings?event_set_id=${set.id}`)).body.items;
  const reportResponse = page.waitForResponse(r => r.url().includes('/analysis/reports?') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Generate reviewed report' }).click();
  const report = await (await reportResponse).json();
  expect(report.content.accepted_findings).toHaveLength(1);
  await page.goto(`/investigations/${id}/reports`);
  await page.getByRole('button').filter({ hasText: report.content_sha256.slice(0, 16) }).click();
  await expect(page.getByRole('dialog')).toBeVisible(); await page.keyboard.press('Escape');
  await page.goto(`/investigations/${id}/events`);
  await page.getByLabel('Evidence to ingest', { exact: true }).selectOption(String(sources[0].item.id));
  await page.getByLabel('Source interpretation profile', { exact: true }).selectOption(String(sources[0].profile.id));
  const repeat = page.waitForResponse(r => r.url().endsWith('/events/runs') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Ingest verified evidence' }).click(); await repeat;
  const after = (await request(page, `/investigations/${id}/events?limit=200`)).body;
  expect(after.items.map((v: { semantic_key: string }) => v.semantic_key).sort()).toEqual(original.items.map((v: { semantic_key: string }) => v.semantic_key).sort());
  await page.goto(`/investigations/${id}/authentication`);
  await page.getByLabel('Saved event set', { exact: true }).selectOption(String(set.id));
  const repeatedDetection = page.waitForResponse(r => r.url().endsWith('/authentication/runs') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Run detections', exact: true }).click();
  expect((await (await repeatedDetection).json()).status).toBe('completed');
  await expect(page.getByRole('heading', { name: '3. Review patterns (5)' })).toBeVisible();
  const rerun = (await request(page, `/investigations/${id}/authentication/findings?event_set_id=${set.id}`)).body.items;
  expect(rerun.map((v: { id: number; status: string }) => [v.id, v.status])).toEqual(before.map((v: { id: number; status: string }) => [v.id, v.status]));
  await page.goto(`/investigations/${id}/exports`);
  await page.getByRole('checkbox', { name: /Verified browser selection/ }).check();
  await page.getByRole('checkbox', { name: /Report #1/ }).check();
  for (const mode of ['metadata', 'originals']) {
    await page.getByLabel('Export mode', { exact: true }).selectOption(mode);
    if (mode === 'originals') await page.getByRole('checkbox', { name: /linux-auth.txt/ }).check();
    const exported = page.waitForResponse(r => r.url().endsWith('/exports') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Create export snapshot' }).click();
    const record = await (await exported).json(); expect(record.status).toBe('completed');
    const downloaded = page.waitForEvent('download');
    await page.getByRole('button', { name: `Download export #${record.id}`, exact: true }).click();
    const path = info.outputPath(`${mode}.zip`); await (await downloaded).saveAs(path);
    const verification = execFileSync(process.env.M6_PYTHON!, ['-m', 'app.ops.archive', path], { cwd: resolve('../backend'), encoding: 'utf8' });
    expect(JSON.parse(verification).valid).toBe(true);
  }
});

test('1000-event browser filtering and pagination stay bounded', async ({ page }, info) => {
  await onboard(page); const id = await createCase(page, 'Synthetic capacity');
  const content = Buffer.from(Array.from({ length: 1000 }, (_, i) => `${new Date(Date.UTC(2026, 10, 5, 12, 0, i)).toISOString()} capacity sshd[${100 + i}]: Failed password for account${i % 20} from 192.0.2.10 port ${2200 + i} ssh2\n`).join(''));
  const item = await upload(page, id, 'capacity.log', content);
  const started = Date.now(); await ingest(page, id, item, 'linux_auth', 'Capacity UTC');
  await expect(page.getByText(/1000 events; showing 1-50/)).toBeVisible();
  const firstPage = Date.now() - started;
  await expect(page.locator('tbody tr')).toHaveCount(50);
  const next = Date.now(); await page.getByRole('button', { name: 'Next events', exact: true }).click();
  await expect(page.getByText(/1000 events; showing 51-100/)).toBeVisible();
  const pagination = Date.now() - next;
  await page.getByLabel('Account', { exact: true }).fill('account1');
  await page.getByRole('button', { name: 'Apply event filters' }).click();
  await expect(page.getByText(/50 events; showing 1-50/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next events', exact: true })).toBeDisabled();
  await info.attach('synthetic-capacity.json', { body: Buffer.from(JSON.stringify({ events: 1000, bytes: content.length, ingestAndFirstRenderMs: firstPage, nextPageMs: pagination, rowsRendered: 50 })), contentType: 'application/json' });
});

test('registration, invalid login, persisted session, logout and case non-disclosure on narrow screens', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const username = await onboard(page); const id = await createCase(page, 'Narrow screen synthetic case');
  await page.reload(); await expect(page.getByRole('heading', { name: 'Narrow screen synthetic case' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await page.getByRole('button', { name: 'Account menu', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Log out', exact: true }).click();
  await expect(page).toHaveURL(/login/);
  await page.getByLabel('Username or email').fill(username); await page.getByLabel('Password', { exact: true }).fill('incorrect-synthetic');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await page.getByLabel('Password', { exact: true }).fill(password); await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).not.toHaveURL(/login/);
  await page.goto(`/investigations/${id + 999999}`); await expect(page.getByText('Investigation not found', { exact: true })).toBeVisible();
});

test('dialog keyboard typing retains focus and traps reverse tab', async ({ page }) => {
  await onboard(page); await page.goto('/investigations');
  await page.getByRole('button', { name: 'New investigation', exact: true }).first().click();
  const dialog = page.getByRole('dialog', { name: 'New investigation' });
  const input = dialog.getByLabel('Title', { exact: true });
  await input.pressSequentially('Keyboard-created case');
  await expect(input).toHaveValue('Keyboard-created case');
  await expect(input).toBeFocused();
  await dialog.getByRole('button', { name: 'Close dialog' }).focus();
  await page.keyboard.press('Shift+Tab');
  await expect(dialog.getByRole('button', { name: 'Create investigation' })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible();
});

test('workspace isolation, analyst restrictions, archived reads and suspension preserve unrelated workspace access', async ({ page, browser }) => {
  test.setTimeout(180_000);
  await onboard(page); const id = await createCase(page, 'Boundary investigation');
  const item = await upload(page, id, 'linux-auth.txt');
  const { run } = await ingest(page, id, item, 'linux_auth', 'Boundary source');
  const set = (await request(page, `/investigations/${id}/authentication/sets`, 'POST', { name: 'Boundary inputs', run_ids: [run.id] })).body;
  expect((await request(page, `/investigations/${id}/authentication/runs`, 'POST', { event_set_id: set.id, configuration: {} })).body.status).toBe('completed');
  const finding = (await request(page, `/investigations/${id}/authentication/findings?event_set_id=${set.id}`)).body.items[0];
  const invitation = (await request(page, '/workspaces/current/invites', 'POST', { role: 'forensic_analyst' })).body;
  const context = await browser.newContext();
  await context.route('**/*', async route => { expect([process.env.M6_WEB_URL, api]).toContain(new URL(route.request().url()).origin); await route.continue(); });
  const member = await context.newPage();
  try {
    const username = await onboard(member);
    const ownWorkspace = (await request(member, '/workspaces')).body[0];
    expect((await request(member, '/workspaces/join', 'POST', { code: invitation.code })).status).toBe(200);
    await member.goto(`/investigations/${id}`);
    await expect(member.getByText('Investigation not found', { exact: true })).toBeVisible();
    const roster = (await request(page, '/workspaces/current/members')).body;
    const actor = roster.find((v: { username: string }) => v.username === username);
    expect((await request(page, `/investigations/${id}/members`, 'POST', { user_id: actor.id, team_role: 'member' })).status).toBe(200);
    await member.reload(); await expect(member.getByRole('heading', { name: 'Boundary investigation' })).toBeVisible();
    expect((await request(member, `/investigations/${id}/analysis/findings/${finding.id}/review`, 'POST', { status: 'accepted' })).status).toBe(403);
    expect((await request(member, `/investigations/${id}/analysis/reports`, 'POST')).status).toBe(403);
    expect((await request(member, `/investigations/${id}/exports`, 'POST', { mode: 'originals', evidence_ids: [item.id] })).status).toBe(403);
    expect((await request(member, `/investigations/${id}/exports`, 'POST', { mode: 'metadata' })).body.status).toBe('completed');
    await member.goto(`/investigations/${id}/evidence/${item.id}`);
    expect((await request(member, `/investigations/${id}/evidence/${item.id}/verify`, 'POST')).status).toBe(403);
    await expect(member.getByRole('button', { name: 'Verify integrity', exact: true })).toBeDisabled();
    await member.goto(`/investigations/${id}/authentication`);
    await member.getByLabel('Saved event set', { exact: true }).selectOption(String(set.id));
    await expect(member.getByRole('button', { name: 'Generate reviewed report' })).toBeDisabled();
    await member.getByRole('region', { name: 'Detection results' }).getByRole('button').filter({ hasText: finding.title }).click();
    await expect(member.getByRole('button', { name: 'Accept finding', exact: true })).toHaveCount(0);
    await member.keyboard.press('Escape');
    expect((await request(page, `/investigations/${id}`, 'PATCH', { status: 'archived' })).status).toBe(200);
    await member.reload(); await member.getByLabel('Saved event set', { exact: true }).selectOption(String(set.id));
    await expect(member.getByRole('button', { name: 'Run detections', exact: true })).toBeDisabled();
    expect((await request(member, `/investigations/${id}/events/runs`, 'POST', { evidence_id: item.id, profile_id: run.profile_id })).status).toBe(403);
    expect((await request(page, `/admin/users/${actor.id}`, 'PATCH', { is_active: false })).status).toBe(200);
    expect([403, 404]).toContain((await request(member, `/investigations/${id}`)).status);
    await member.getByRole('button', { name: 'Account menu' }).click();
    await member.getByRole('menuitem', { name: 'Switch workspace', exact: true }).click();
    await member.getByRole('button', { name: ownWorkspace.name, exact: true }).click();
    await expect(member).not.toHaveURL(/onboarding/);
    await createCase(member, 'Unrelated workspace remains usable');
    expect((await request(member, `/investigations/${id}`)).status).toBe(404);
  } finally { await context.close(); }
});

test('unsupported ingestion and interrupted browser downloads remain visible and retryable', async ({ page }, info) => {
  await onboard(page); const id = await createCase(page, 'Recovery boundaries');
  const item = await upload(page, id, 'linux-auth.txt');
  await page.goto(`/investigations/${id}/events`);
  await page.getByRole('button', { name: 'Configure source profile' }).click();
  await page.getByLabel('Profile name').fill('Deliberately unsupported interpretation');
  await page.getByLabel('Adapter', { exact: true }).selectOption('windows_security');
  await page.getByRole('button', { name: 'Save source profile' }).click();
  await page.getByLabel('Evidence to ingest').selectOption(String(item.id));
  await page.getByRole('button', { name: 'Ingest verified evidence' }).click();
  await expect(page.getByRole('status').filter({ hasText: /rejected|failed|partial/ })).toBeVisible();
  await page.goto(`/investigations/${id}/exports`);
  const pending = page.waitForResponse(r => r.url().endsWith('/exports') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Create export snapshot' }).click();
  const record = await (await pending).json(); expect(record.status).toBe('completed');
  // Explicit isolated network-failure test, not a substitute for the real workflow.
  await page.route('**/exports/*/download', route => route.abort('failed'), { times: 1 });
  await page.getByRole('button', { name: `Download export #${record.id}` }).click();
  await expect(page.getByText('Cannot reach the Provena backend. Check the API is running, then retry.', { exact: true })).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: `Download export #${record.id}` }).click();
  await (await download).saveAs(info.outputPath('recovered.zip'));
  expect((await request(page, `/investigations/${id}/exports`)).body).toHaveLength(1);
  await page.getByRole('button', { name: `Recover interrupted or prune expired #${record.id}` }).click();
  await expect(page.getByText(`Export #${record.id} · metadata · completed`, { exact: true })).toBeVisible();
});
