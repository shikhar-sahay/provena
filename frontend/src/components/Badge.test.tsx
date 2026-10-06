// Behavior tests for status badges: state is always labeled, never color-only.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IntegrityBadge, PriorityBadge, StatusBadge } from "./Badge";

describe("StatusBadge", () => {
  it("labels each investigation status", () => {
    const { rerender } = render(<StatusBadge status="open" />);
    expect(screen.getByText("Open")).toBeInTheDocument();
    rerender(<StatusBadge status="in_progress" />);
    expect(screen.getByText("In progress")).toBeInTheDocument();
    rerender(<StatusBadge status="archived" />);
    expect(screen.getByText("Archived")).toBeInTheDocument();
  });
});

describe("IntegrityBadge", () => {
  it("states mismatch plainly", () => {
    render(<IntegrityBadge status="mismatch" />);
    expect(screen.getByText("Mismatch detected")).toBeInTheDocument();
  });

  it("distinguishes baseline creation from verification", () => {
    render(<IntegrityBadge status="not_verified" />);
    expect(screen.getByText("Not verified")).toBeInTheDocument();
  });
});

describe("PriorityBadge", () => {
  it("labels critical priority", () => {
    render(<PriorityBadge priority="critical" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });
});
