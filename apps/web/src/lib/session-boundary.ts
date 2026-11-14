"use client";

// UX redaction only. The backend remains the authority for every request.
// Persist a fixed-size non-sensitive record, never a token, identity or cargo.
export const SESSION_BOUNDARY_KEY = "cargopulse.session-boundary.v1";
export const SESSION_BOUNDARY_EVENT = "cargopulse:session-hidden";
export type BoundaryReason = "logout" | "expired" | "offline" | "return" | "unavailable" | "signin" | "other-tab";
type Boundary = { v: 1; epoch: string; fingerprint: string; state: 0 | 1 | 2 };
const UNKNOWN = "0".repeat(64);
let fingerprint: string | null = null;

export function readSessionBoundary(): Boundary {
  const raw = localStorage.getItem(SESSION_BOUNDARY_KEY);
  const value: Boundary = raw ? JSON.parse(raw) : {
    v: 1, epoch: crypto.randomUUID(), fingerprint: UNKNOWN, state: 0,
  };
  if (value.v !== 1 || !/^[a-f0-9-]{36}$/.test(value.epoch) ||
      !/^[a-f0-9]{64}$/.test(value.fingerprint) || ![0, 1, 2].includes(value.state)) {
    throw new Error("Session verification unavailable");
  }
  // Reserve the complete record before showing private UI. Later invalidations
  // replace the same byte count, including when storage is otherwise full.
  localStorage.setItem(SESSION_BOUNDARY_KEY, JSON.stringify(value));
  return value;
}

function writeBoundary(state: Boundary["state"], hash: string) {
  const value: Boundary = { v: 1, epoch: crypto.randomUUID(), fingerprint: hash, state };
  localStorage.setItem(SESSION_BOUNDARY_KEY, JSON.stringify(value));
}

export function hideSession(reason: BoundaryReason) {
  try {
    const current = readSessionBoundary();
    writeBoundary(1, fingerprint ?? current.fingerprint);
  } catch {
    // Still redact this document. A new document fails closed if storage cannot
    // be read/written; no claim about server revocation follows from this event.
  }
  window.dispatchEvent(new CustomEvent(SESSION_BOUNDARY_EVENT, { detail: reason }));
}

export async function sessionFetch(input: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(input, init);
  if (response.status === 401) hideSession("expired");
  return response;
}

type VerifiedSession = { fingerprint: string; deadline: number };

async function sessionFingerprint(signal?: AbortSignal): Promise<VerifiedSession | null> {
  const started = performance.now();
  const response = await sessionFetch("/api/v1/auth/csrf", {
    credentials: "same-origin", cache: "no-store",
    signal: signal ?? AbortSignal.timeout(5000),
  });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error("Session verification unavailable");
  const lifetime = response.headers.get("x-session-expires-in");
  // Bound to the browser's timer range; reject absent, fractional, negative or
  // otherwise ambiguous metadata rather than leaving private DOM open forever.
  if (!lifetime || !/^(0|[1-9][0-9]{0,6})$/.test(lifetime) || Number(lifetime) > 2_147_483) {
    throw new Error("Session verification unavailable");
  }
  // The server reports floor(remaining seconds), without renewing its session.
  // Start from request initiation to subtract the entire RTT conservatively.
  const deadline = started + Number(lifetime) * 1000;
  if (deadline <= performance.now()) {
    hideSession("expired");
    throw new Error("Session verification unavailable");
  }
  const body = await response.json();
  if (typeof body.csrf !== "string" || !body.csrf || body.csrf.length > 256) {
    throw new Error("Session verification unavailable");
  }
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(body.csrf));
  if (deadline <= performance.now()) {
    hideSession("expired");
    throw new Error("Session verification unavailable");
  }
  return {
    fingerprint: Array.from(new Uint8Array(hash), (byte) => byte.toString(16).padStart(2, "0")).join(""),
    deadline,
  };
}

export async function verifyWorkspaceSession(signal?: AbortSignal): Promise<number | null> {
  const before = readSessionBoundary();
  if (!navigator.onLine) { hideSession("offline"); return null; }
  const verified = await sessionFingerprint(signal);
  if (!verified) return null;
  const hash = verified.fingerprint;
  const current = readSessionBoundary();
  // Do not reveal a response from before another tab changed the session.
  if (current.epoch !== before.epoch && current.fingerprint !== hash) return null;
  // An old session cannot reopen the workspace after a local privacy boundary.
  // State 2 is set only after the explicit SSO preflight received a server 401.
  if (current.state === 1 && (current.fingerprint === UNKNOWN || current.fingerprint === hash)) {
    return null;
  }
  fingerprint = hash;
  writeBoundary(0, hash);
  return verified.deadline;
}

export async function prepareOrganisationSignIn() {
  hideSession("signin");
  const verified = await sessionFingerprint();
  writeBoundary(verified ? 1 : 2, verified?.fingerprint ?? UNKNOWN);
}

export async function confirmDevelopmentSignIn() {
  // Call only after an explicit successful POST /auth/development. Its new
  // session is checked again; no reconnect event can invoke this reset.
  const verified = await sessionFingerprint();
  if (!verified) throw new Error("Sign in again before opening the workspace");
  fingerprint = verified.fingerprint;
  writeBoundary(0, verified.fingerprint);
}
