import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { api } from "../api/client";
import UsersPage from "./UsersPage";

vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ user: { id: 1, role: "admin" } }) }));
vi.mock("../components/Toast", () => ({ useToast: () => ({ notify: vi.fn() }) }));
vi.mock("../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../api/client")>();
  return { ...original, api: { ...original.api, adminListUsers: vi.fn(), adminSetActive: vi.fn() } };
});

it("suspends and restores workspace access without promising global sign-in blocking", async () => {
  const member = { id: 2, username: "analyst", email: "a@example.test", full_name: "Analyst",
    role: "investigator" as const, is_active: true, created_at: "2026-01-01T00:00:00Z", investigations: [] };
  vi.mocked(api.adminListUsers).mockResolvedValue([member]);
  vi.mocked(api.adminSetActive).mockResolvedValueOnce({ ...member, is_active: false }).mockResolvedValueOnce(member);
  render(<MemoryRouter><UsersPage /></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: "Suspend access" }));
  await waitFor(() => expect(api.adminSetActive).toHaveBeenCalledWith(2, false));
  expect(await screen.findByText("Suspended")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Restore access" }));
  await waitFor(() => expect(api.adminSetActive).toHaveBeenCalledWith(2, true));
  expect(await screen.findByRole("button", { name: "Suspend access" })).toBeInTheDocument();
  expect(screen.getByText(/Sign-in and other workspaces remain available/)).toBeInTheDocument();
});
