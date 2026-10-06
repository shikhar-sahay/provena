// Behavior tests for formatting helpers used across the interface.

import { describe, expect, it } from "vitest";
import { displayName, formatBytes, timeAgo } from "./format";

describe("formatBytes", () => {
  it("formats bytes and larger units", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(823)).toBe("823 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});

describe("timeAgo", () => {
  it("renders relative times for recent dates", () => {
    const now = Date.now();
    expect(timeAgo(new Date(now - 30_000).toISOString())).toBe("just now");
    expect(timeAgo(new Date(now - 5 * 60_000).toISOString())).toBe("5m ago");
    expect(timeAgo(new Date(now - 3 * 3_600_000).toISOString())).toBe("3h ago");
    expect(timeAgo(new Date(now - 2 * 86_400_000).toISOString())).toBe("2d ago");
  });
});

describe("displayName", () => {
  it("prefers the full name and falls back to the username", () => {
    expect(displayName({ full_name: "Case Investigator", username: "investigator" })).toBe(
      "Case Investigator",
    );
    expect(displayName({ full_name: "", username: "analyst" })).toBe("analyst");
  });
});
