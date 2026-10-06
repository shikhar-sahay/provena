// Human error semantics: distinguish invalid credentials, backend outages,
// and server failures instead of showing raw status codes.

import { ApiError } from "../api/client";

export type ErrorKind = "credentials" | "offline" | "forbidden" | "not-found" | "server" | "other";

export function classifyError(error: unknown): ErrorKind {
  if (error instanceof ApiError) {
    if (error.status === 401) return "credentials";
    if (error.status === 403) return "forbidden";
    if (error.status === 404) return "not-found";
    if (error.status >= 500) return "server";
    return "other";
  }
  if (error instanceof TypeError) return "offline";
  return "other";
}

export function loginErrorMessage(error: unknown): string {
  switch (classifyError(error)) {
    case "credentials":
      return "Invalid username or password. Check your details and try again.";
    case "offline":
      return "Cannot reach the Provena backend. Start the API on :8000, then retry.";
    case "server":
      return "The server hit a problem signing you in. Try again in a moment.";
    default:
      return error instanceof ApiError ? error.message : "Sign-in failed. Try again.";
  }
}

export function actionErrorMessage(error: unknown, fallback: string): string {
  switch (classifyError(error)) {
    case "offline":
      return "Cannot reach the Provena backend. Check the API is running, then retry.";
    case "forbidden":
      return "Your role does not permit this action.";
    case "not-found":
      return "The item was not found, or you no longer have access to it.";
    case "server":
      return "The server hit a problem. Try again in a moment.";
    default:
      return error instanceof ApiError ? error.message : fallback;
  }
}
