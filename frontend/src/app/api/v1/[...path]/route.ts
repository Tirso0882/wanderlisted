import { auth } from "@clerk/nextjs/server";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

type ProxyContext = {
  params: Promise<{ path: string[] }>;
};

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function copyEndToEndHeaders(source: Headers): Headers {
  const headers = new Headers();
  source.forEach((value, name) => {
    if (!HOP_BY_HOP_HEADERS.has(name.toLowerCase())) {
      headers.set(name, value);
    }
  });
  return headers;
}

function configuredApiUrl(): URL | null {
  const raw = process.env.API_URL?.trim();
  if (!raw) return null;

  try {
    const url = new URL(raw);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    return url;
  } catch {
    return null;
  }
}

function clerkConfigured(): boolean {
  return (
    process.env.CLERK_ENABLED?.trim().toLowerCase() === "true" &&
    Boolean(
      (
        process.env.CLERK_PUBLISHABLE_KEY ??
        process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
      )?.trim(),
    ) &&
    Boolean(process.env.CLERK_SECRET_KEY?.trim())
  );
}

async function proxy(request: Request, context: ProxyContext): Promise<Response> {
  const apiUrl = configuredApiUrl();
  if (!apiUrl) {
    return Response.json(
      { detail: "API upstream is not configured." },
      { status: 503 },
    );
  }

  const { path } = await context.params;
  const encodedPath = path.map(encodeURIComponent).join("/");
  const upstreamUrl = new URL(`/api/v1/${encodedPath}`, apiUrl);
  upstreamUrl.search = new URL(request.url).search;

  const requestHeaders = copyEndToEndHeaders(request.headers);
  requestHeaders.delete("host");
  // Browser-supplied bearer credentials never cross this trust boundary.
  // When Clerk is enabled, only the token read from the server-side Clerk
  // session is forwarded to FastAPI.
  requestHeaders.delete("authorization");

  if (clerkConfigured()) {
    try {
      const session = await auth();
      const token = await session.getToken();
      if (token) requestHeaders.set("authorization", `Bearer ${token}`);
    } catch {
      return Response.json(
        { detail: "Account authentication is unavailable." },
        { status: 503 },
      );
    }
  }

  try {
    const body =
      request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.arrayBuffer();
    const upstreamResponse = await fetch(upstreamUrl, {
      method: request.method,
      headers: requestHeaders,
      body,
      cache: "no-store",
      redirect: "manual",
      signal: request.signal,
    });

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: copyEndToEndHeaders(upstreamResponse.headers),
    });
  } catch {
    return Response.json(
      { detail: "API upstream is unavailable." },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const HEAD = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
