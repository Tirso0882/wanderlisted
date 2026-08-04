import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";

function clerkEnabled(): boolean {
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

export function proxy(request: NextRequest, event: NextFetchEvent) {
  if (!clerkEnabled()) return NextResponse.next();
  const middleware = clerkMiddleware({
    publishableKey:
      process.env.CLERK_PUBLISHABLE_KEY ??
      process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
    secretKey: process.env.CLERK_SECRET_KEY,
  });
  return middleware(request, event);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
