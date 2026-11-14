import type { Model } from "./types";
import { sessionFetch } from "./session-boundary";
export class ApiError extends Error {
  constructor(
    public status: number,
    public problem: Partial<Model<"Problem">>,
  ) {
    super(problem.detail || problem.title || `Request failed (${status})`);
  }
}
export async function api<T>(
  path: string,
  options: {
    method?: "POST";
    body?: unknown;
    etag?: string;
    signal?: AbortSignal;
  } = {},
): Promise<T> {
  const headers = new Headers({
    Accept: "application/json",
    "X-Correlation-ID": crypto.randomUUID(),
  });
  if (options.method === "POST") {
    // Development login precedes a session and is protected by strict server
    // Origin checks. Every authenticated command still requires session-bound CSRF.
    if (path !== "/auth/development") {
      const refresh = await sessionFetch("/api/v1/auth/csrf", {
        credentials: "same-origin", cache: "no-store",
        signal: options.signal ?? AbortSignal.timeout(15000),
      });
      if (!refresh.ok) throw new ApiError(refresh.status, {
        title: "Session verification unavailable", detail: "Sign in again before submitting a command.",
      });
      const { csrf } = await refresh.json();
      if (typeof csrf !== "string" || !csrf || csrf.length > 256) throw new ApiError(403, {
        title: "Session verification unavailable", detail: "Refresh your session before submitting a command.",
      });
      headers.set("X-CSRF-Token", csrf);
    }
    headers.set("Idempotency-Key", crypto.randomUUID());
    if (options.body !== undefined && !(options.body instanceof FormData))
      headers.set("Content-Type", "application/json");
    if (options.etag) headers.set("If-Match", options.etag);
  }
  let response: Response;
  try {
    response = await sessionFetch(`/api/v1${path}`, {
      method: options.method || "GET",
      headers,
      body:
        options.body === undefined
          ? undefined
          : options.body instanceof FormData
            ? options.body
            : JSON.stringify(options.body),
      credentials: "same-origin",
      cache: "no-store",
      signal: options.signal,
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError(503, {
      title: "Service unavailable",
      detail: "The service could not be reached. No result has been confirmed.",
    });
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, body);
  return body as T;
}
