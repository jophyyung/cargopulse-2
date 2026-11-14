import { NextRequest } from "next/server";
import { apiOrigin } from "@/lib/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const reads =
  /^(me|events|fixtures\/recover|policies|metrics|audit|health\/(live|ready)|auth\/(csrf|login|callback)|imports\/[a-f0-9-]+|scenarios\/[a-f0-9-]+(?:\/(candidates|urgency))?|policies\/[a-f0-9-]+|reports\/[a-f0-9-]+\/export|jobs\/[a-f0-9-]+|plans\/[a-f0-9-]+(?:\/alternatives)?|protect\/sandbox)$/;
const writes =
  /^(auth\/(development|logout)|imports\/(validate|upload-csv)|policies\/drafts|policies\/[a-f0-9-]+\/publish|imports\/[a-f0-9-]+\/commit|scenarios|scenarios\/[a-f0-9-]+\/(solve|supersede)|plans\/[a-f0-9-]+\/decisions)$/;

class BoundedBodyError extends Error {
  constructor(readonly status: number) { super("Bounded request body rejected"); }
}

async function readBoundedBody(request: NextRequest, maximum: number): Promise<ArrayBuffer> {
  if (!request.body) return new ArrayBuffer(0);
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  let interrupted = false;
  const stop = () => { interrupted = true; void reader.cancel(); };
  const timer = setTimeout(stop, 15_000);
  request.signal.addEventListener("abort", stop, { once: true });
  try {
    while (true) {
      if (request.signal.aborted) throw new BoundedBodyError(408);
      const { done, value } = await reader.read();
      if (interrupted) throw new BoundedBodyError(408);
      if (done) break;
      size += value.byteLength;
      if (size > maximum) {
        await reader.cancel();
        throw new BoundedBodyError(413);
      }
      chunks.push(value);
    }
  } finally {
    clearTimeout(timer);
    request.signal.removeEventListener("abort", stop);
    reader.releaseLock();
  }
  const output = new ArrayBuffer(size);
  const view = new Uint8Array(output);
  let offset = 0;
  for (const chunk of chunks) { view.set(chunk, offset); offset += chunk.byteLength; }
  return output;
}
async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const path = (await context.params).path.join("/");
  if (!(request.method === "GET" ? reads : writes).test(path))
    return Response.json(
      {
        title: "Not available",
        detail: "This endpoint is not enabled.",
        status: 404,
      },
      { status: 404 },
    );
  if (
    path === "auth/development" &&
    process.env.CARGOPULSE_ENV !== "development"
  )
    return Response.json(
      { title: "Not available", status: 404 },
      { status: 404 },
    );
  const headers = new Headers();
  for (const key of [
    "cookie",
    "content-type",
    "accept",
    "origin",
    "x-csrf-token",
    "idempotency-key",
    "if-match",
    "x-correlation-id",
  ]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  try {
    const max = 8 * 1024 * 1024;
    if (Number(request.headers.get("content-length") || 0) > max)
      return new Response("Request too large", { status: 413 });
    const body =
      request.method === "POST" ? await readBoundedBody(request, max) : undefined;
    if (body && body.byteLength > max)
      return new Response("Request too large", { status: 413 });
    const upstream = await fetch(
      `${apiOrigin()}/api/v1/${path}${request.nextUrl.search}`,
      {
        method: request.method,
        headers,
        body,
        redirect: "manual",
        cache: "no-store",
        // Urgency analysis recomputes routes at every cutoff; allow it longer than other reads.
        signal: AbortSignal.timeout(/\/urgency$/.test(path) ? 60000 : 15000),
      },
    );
    const outgoing = new Headers({ "Cache-Control": "no-store" });
    for (const key of [
      "content-type",
      "location",
      "etag",
      "retry-after",
      "x-correlation-id",
      "content-disposition",
      "x-session-expires-in",
    ]) {
      const value = upstream.headers.get(key);
      if (value) outgoing.set(key, value);
    }
    for (const cookie of upstream.headers.getSetCookie())
      outgoing.append("Set-Cookie", cookie);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: outgoing,
    });
  } catch (error) {
    if (error instanceof BoundedBodyError) {
      return Response.json({ title: "Request body rejected", status: error.status }, { status: error.status });
    }
    return Response.json(
      {
        title: "Service unavailable",
        detail:
          "The operational service is unavailable. Retry when connectivity is restored.",
        code: "DEPENDENCY_NOT_READY",
        status: 503,
      },
      { status: 503 },
    );
  }
}
export { forward as GET, forward as POST };
