import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { api } from "../api/client";
import OnboardingPage from "./OnboardingPage";
import { ThemeProvider } from "../theme/ThemeContext";

const refresh = vi.fn();
vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ refresh, logout: vi.fn() }) }));
vi.mock("../api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("../api/client")>();
  return { ...original, api: { ...original.api, listWorkspaces: vi.fn(), selectWorkspace: vi.fn() } };
});

it("lets a suspended member continue in an unrelated available workspace", async () => {
  vi.mocked(api.listWorkspaces).mockResolvedValue([{ id: 9, name: "Available lab" } as Awaited<ReturnType<typeof api.listWorkspaces>>[number]]);
  render(<ThemeProvider><MemoryRouter><OnboardingPage /></MemoryRouter></ThemeProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Available lab" }));
  await waitFor(() => expect(api.selectWorkspace).toHaveBeenCalledWith(9));
  await waitFor(() => expect(refresh).toHaveBeenCalled());
});
