import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Dialog } from "./Dialog";

describe("Dialog report reader", () => {
  it("provides a bounded scrolling reader while preserving a printable content region", () => {
    render(
      <Dialog open onClose={() => undefined} title="RPT-0001" reader>
        <article>Long immutable report</article>
      </Dialog>,
    );

    const dialog = screen.getByRole("dialog", { name: "RPT-0001" });
    expect(dialog).toHaveClass(
      "report-reader",
      "max-w-5xl",
      "max-h-[calc(100dvh-1rem)]",
      "sm:max-h-[calc(100dvh-2rem)]",
    );
    const reader = screen.getByLabelText("Report content");
    expect(reader).toHaveAttribute("tabindex", "0");
    expect(reader).toHaveClass(
      "report-reader-body",
      "overflow-y-auto",
    );
  });
});
