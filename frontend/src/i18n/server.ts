import "server-only";

import { cookies, headers } from "next/headers";
import { cache } from "react";
import {
  isAppLocale,
  messagesByLocale,
  resolveInitialLocale,
  type AppLocale,
} from "./config";

export const LOCALE_COOKIE = "wanderlisted_locale";

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

function configuredApiUrl(): URL | null {
  try {
    const url = new URL(process.env.API_URL?.trim() ?? "");
    return url.protocol === "http:" || url.protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

async function getAccountLocale(): Promise<AppLocale | null> {
  const apiUrl = configuredApiUrl();
  if (!clerkConfigured() || !apiUrl) return null;

  try {
    const { auth } = await import("@clerk/nextjs/server");
    const session = await auth();
    const token = await session.getToken();
    if (!token) return null;
    const response = await fetch(new URL("/api/v1/account/preferences", apiUrl), {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(1_500),
    });
    if (!response.ok) return null;
    const preference = (await response.json()) as { locale?: unknown };
    return isAppLocale(preference.locale) ? preference.locale : null;
  } catch {
    return null;
  }
}

export const getRequestLocale = cache(async () => {
  const [accountLocale, cookieStore, headerStore] = await Promise.all([
    getAccountLocale(),
    cookies(),
    headers(),
  ]);
  return resolveInitialLocale(
    accountLocale,
    cookieStore.get(LOCALE_COOKIE)?.value,
    headerStore.get("accept-language"),
  );
});

export async function getRequestMessages() {
  const locale = await getRequestLocale();
  return { locale, messages: messagesByLocale[locale] };
}
