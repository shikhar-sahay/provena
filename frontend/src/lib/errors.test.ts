// Behavior tests for error semantics: the UI must distinguish expired
// sessions, outages, and server failures instead of showing raw codes.

import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { actionErrorMessage, classifyError, loginErrorMessage } from "./errors";

describe("classifyError", () => {
  it("maps API failures to kinds", () => {
    expect(classifyError(new ApiError(401, "x"))).toBe("credentials");
    expect(classifyError(new ApiError(403, "x"))).toBe("forbidden");
    expect(classifyError(new ApiError(404, "x"))).toBe("not-found");
    expect(classifyError(new ApiError(500, "x"))).toBe("server");
    expect(classifyError(new ApiError(422, "x"))).toBe("other");
  });

  it("treats network failures as offline", () => {
    expect(classifyError(new TypeError("Failed to fetch"))).toBe("offline");
  });
});

describe("loginErrorMessage", () => {
  it("explains bad credentials without jargon", () => {
    expect(loginErrorMessage(new ApiError(401, "Invalid credentials."))).toContain(
      "Invalid username or password",
    );
  });

  it("points at the backend when it is unreachable", () => {
    expect(loginErrorMessage(new TypeError("Failed to fetch"))).toContain(":8000");
  });

  it("never leaks raw status codes for server failures", () => {
    const message = loginErrorMessage(new ApiError(502, "Bad Gateway"));
    expect(message).not.toContain("502");
    expect(message).not.toContain("Bad Gateway");
  });
});

describe("actionErrorMessage", () => {
  it("explains permission denials", () => {
    expect(actionErrorMessage(new ApiError(403, "Forbidden"), "fallback")).toContain("role");
  });

  it("uses the fallback only for unclassified errors", () => {
    expect(actionErrorMessage(new Error("boom"), "fallback")).toBe("fallback");
  });
});
