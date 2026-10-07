import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import ReportsPage from "./ReportsPage";

let role = "investigator";

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { role } }),
}));

vi.mock("../components/Toast", () => ({
  useToast: () => ({ notify: vi.fn() }),
}));

vi.mock("../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../api/client")>();
  return { ...original, api: { ...original.api, listReports: vi.fn(), generateReport: vi.fn() } };
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/investigations/7/reports"]}>
      <Routes>
        <Route path="/investigations/:id/reports" element={<ReportsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ReportsPage states", () => {
  beforeEach(() => {
    role = "investigator";
    vi.mocked(api.listReports).mockReset();
  });

  it("renders an empty state", async () => {
    vi.mocked(api.listReports).mockResolvedValueOnce([]);
    renderPage();
    expect(await screen.findByText("No reports yet")).toBeInTheDocument();
  });

  it("renders an actionable API error", async () => {
    vi.mocked(api.listReports).mockRejectedValueOnce(new Error("offline"));
    renderPage();
    expect(await screen.findByText("Could not load reports.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("does not offer report generation to an analyst", async () => {
    role = "forensic_analyst";
    vi.mocked(api.listReports).mockResolvedValueOnce([]);
    renderPage();
    await screen.findByText("No reports yet");
    expect(screen.queryByRole("button", { name: "Generate report" })).not.toBeInTheDocument();
  });
});
