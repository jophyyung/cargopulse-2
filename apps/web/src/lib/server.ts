import "server-only";
import { cookies } from "next/headers";
import type { Principal } from "./types";
export function apiOrigin() {
  const target = new URL(
    process.env.API_INTERNAL_URL || "http://127.0.0.1:8000",
  );
  if (
    !["http:", "https:"].includes(target.protocol) ||
    target.username ||
    target.password ||
    target.pathname !== "/" ||
    target.search ||
    target.hash
  )
    throw new Error("API_INTERNAL_URL must be an HTTP origin");
  return target.origin;
}
export async function principal(): Promise<{
  user: Principal | null;
  unavailable: boolean;
}> {
  try {
    const result = await fetch(`${apiOrigin()}/api/v1/me`, {
      headers: { Cookie: (await cookies()).toString() },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (result.status === 401) return { user: null, unavailable: false };
    if (!result.ok) return { user: null, unavailable: true };
    return { user: (await result.json()) as Principal, unavailable: false };
  } catch {
    return { user: null, unavailable: true };
  }
}
