import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { EventProfileForm } from "../components/EventProfileForm";
import { EventCoverageView } from "../components/EventCoverageView";
import { EventExplorer, EventDetail } from "./EventsPage";
import { api, eventApi } from "../api/client";
import type { EventPage, EventRun, SecurityEvent } from "../api/client";
vi.mock("../api/client", async (importOriginal) => ({ ...(await importOriginal<typeof import("../api/client")>()), api: { listEvidence: vi.fn() }, eventApi: {
  profiles: vi.fn(), runs: vi.fn(), list: vi.fn(), detail: vi.fn(), createProfile: vi.fn(), ingest: vi.fn(), recover: vi.fn(),
} }));
const row = { id: 1, semantic_key: "a".repeat(64), evidence_id: 2, evidence_number: "E-002", first_run_id: 3,
  profile_id: 4, input_sha256: "b".repeat(64), record_fingerprint: "c".repeat(64), provider: "sshd", category: "authentication",
  event_type: "logon", outcome: "failure", event_id: null, username: "mira", account_domain: null, hostname: "lab-host",
  source_ip: "192.0.2.1", destination_ip: null, source_port: 22, destination_port: null,
  original_timestamp: "Nov  5 12:00:00", timestamp_utc: null,
  time_semantics: { certainty: "unknown", precision: "second", assumptions: [], warnings: [] }, attributes: { process_id: "123" },
  warnings: ["Timezone unknown"], locator: { kind: "line", line: 7 }, profile_snapshot: { version: "1" },
  adapter_version: "1.1", normalization_version: "1.tz2026.6", coverage_status: "partial", support_verified: false } satisfies SecurityEvent;
const run = { id: 3, evidence_id: 2, profile_id: 4, status: "partial", input_sha256: row.input_sha256, verification_id: 7,
  coverage: { records_total: 5, recognized: 2, unrecognized: 1, rejected: 1, omitted: 1, events_created: 2, warnings: ["Partial coverage"] }, error: null, created_at: "2026-11-05T12:00:00Z" } satisfies EventRun;
const page = { items: [row], total: 51, limit: 50, offset: 0, time_policy: "Unknown times excluded from UTC ranges", view_policy: "Historical interpretations" } satisfies EventPage;

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.listEvidence).mockResolvedValue([]);
  vi.mocked(eventApi.profiles).mockResolvedValue([]);
  vi.mocked(eventApi.runs).mockResolvedValue({ items: [run], total: 1, limit: 25, offset: 0 });
  vi.mocked(eventApi.list).mockResolvedValue(page);
  vi.mocked(eventApi.detail).mockResolvedValue(row);
});

it("configures immutable profiles without inventing a year or timezone", async () => {
  const save = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  render(<EventProfileForm save={save} busy={false} />);
  await user.type(screen.getByLabelText("Profile name"), "Linux unknown time");
  await user.click(screen.getByRole("button", { name: "Save source profile" }));
  expect(save).toHaveBeenCalledWith("Linux unknown time", expect.objectContaining({ adapter: "linux_auth", year: null, timezone: null }));
  await user.selectOptions(screen.getByLabelText("Adapter"), "windows_security");
  expect(screen.queryByLabelText("Year for yearless syslog (optional)")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Source format")).toHaveValue("jsonl");
  expect(screen.getByText(/Native EVTX/)).toBeInTheDocument();
});

it("shows coverage accounting, uncertain time and evidence provenance", () => {
  render(<MemoryRouter><EventCoverageView run={run} /><EventDetail event={row} invId={1} /></MemoryRouter>);
  expect(screen.getByText(/recognized 2; unsupported 1; rejected 1; omitted 1/)).toBeInTheDocument();
  expect(screen.getByText("UTC projection: Not established")).toBeInTheDocument();
  expect(screen.getByText(row.input_sha256)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Open source evidence/ })).toHaveAttribute("href", "/investigations/1/evidence/2");
  expect(screen.getByRole("alert")).toHaveTextContent("not currently verified");
});

it("applies server filters, paginates and opens details", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><EventExplorer invId={1} canIngest={false} /></MemoryRouter>);
  await screen.findByText("mira");
  await user.selectOptions(screen.getByLabelText("Outcome"), "failure");
  await user.type(screen.getByLabelText("Account"), "mira");
  await user.click(screen.getByRole("button", { name: "Apply event filters" }));
  await waitFor(() => expect(eventApi.list).toHaveBeenLastCalledWith(1, expect.objectContaining({ outcome: "failure", username: "mira" }), 0));
  await user.click(screen.getByRole("button", { name: "Next events" }));
  await waitFor(() => expect(eventApi.list).toHaveBeenLastCalledWith(1, expect.anything(), 50));
  await user.click(screen.getByRole("button", { name: "Inspect event" }));
  expect(await screen.findByText("Normalized event provenance")).toBeInTheDocument();
  expect(eventApi.detail).toHaveBeenCalledWith(1, row.semantic_key);
});

it("renders empty and safe error states", async () => {
  vi.mocked(eventApi.list).mockResolvedValue({ ...page, items: [], total: 0 });
  const view = render(<MemoryRouter><EventExplorer invId={1} canIngest={false} /></MemoryRouter>);
  await screen.findByText("No matching security events");
  view.unmount();
  vi.mocked(eventApi.list).mockRejectedValue(new Error("offline"));
  render(<MemoryRouter><EventExplorer invId={1} canIngest={false} /></MemoryRouter>);
  await screen.findByText("Could not load security events.");
});

it("requires verified registration before ingest and reports retry outcomes", async () => {
  const user = userEvent.setup();
  vi.mocked(api.listEvidence).mockResolvedValue([{ id: 2, evidence_number: "E-002", title: "Auth log", registration_status: "ready", integrity_status: "verified" }] as never);
  vi.mocked(eventApi.profiles).mockResolvedValue([{ id: 4, name: "Linux", semantic_key: "d".repeat(64), version: "1", configuration: { adapter: "linux_auth", format: "syslog", encoding: "utf-8", timezone: null, year: null, source_host: null, timestamp_convention: "source" } }]);
  vi.mocked(eventApi.ingest).mockResolvedValue({ ...run, coverage: { ...run.coverage, events_created: 0 } });
  render(<MemoryRouter><EventExplorer invId={1} canIngest /></MemoryRouter>);
  await screen.findByText("mira");
  expect(screen.getByRole("button", { name: "Ingest verified evidence" })).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Evidence to ingest"), "2");
  await user.selectOptions(screen.getByLabelText("Source interpretation profile"), "4");
  await user.click(screen.getByRole("button", { name: "Ingest verified evidence" }));
  expect(eventApi.ingest).toHaveBeenCalledWith(1, 2, 4);
  expect(await screen.findByRole("status")).toHaveTextContent("new events 0");
});
