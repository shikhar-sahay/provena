import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { EvidenceStatus } from "./EvidenceStatus";

it("distinguishes incomplete registration from verification and recovery states", () => {
  const recover = vi.fn();
  const { rerender } = render(<EvidenceStatus registration="pending" integrity="not_verified" onRecover={recover} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Registration pending");
  fireEvent.click(screen.getByRole("button", { name: "Recover registration" }));
  expect(recover).toHaveBeenCalledOnce();
  rerender(<EvidenceStatus registration="failed" integrity="unavailable" />);
  expect(screen.getByRole("alert")).toHaveTextContent("Registration failed");
  rerender(<EvidenceStatus registration="ready" integrity="not_verified" />);
  expect(screen.getByRole("status")).toHaveTextContent("Registered successfully");
  rerender(<EvidenceStatus integrity="verified" />);
  expect(screen.getByRole("status")).toHaveTextContent("private copy");
  rerender(<EvidenceStatus integrity="mismatch" />);
  expect(screen.getByRole("status")).toHaveTextContent("do not replace its baseline");
  rerender(<EvidenceStatus integrity="unavailable" />);
  expect(screen.getByRole("status")).toHaveTextContent("restore the original bytes");
});
