import type { AppLocale } from "@/i18n/config";
import type {
  AccountPreferencesResponse,
  SessionListResponse,
  SessionSnapshot,
} from "@/lib/types";
import { apiDelete, apiGet, apiPost, apiPut } from "./client";

const BROWSER_SESSIONS_KEY = "wanderlisted-browser-sessions";

export function browserSessionIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const value: unknown = JSON.parse(
      window.localStorage.getItem(BROWSER_SESSIONS_KEY) ?? "[]",
    );
    return Array.isArray(value)
      ? value.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

export function rememberBrowserSession(sessionId: string): void {
  if (typeof window === "undefined") return;
  const existing = browserSessionIds();
  if (existing.includes(sessionId)) return;
  window.localStorage.setItem(
    BROWSER_SESSIONS_KEY,
    JSON.stringify([...existing, sessionId].slice(-50)),
  );
}

export function forgetBrowserSession(sessionId: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    BROWSER_SESSIONS_KEY,
    JSON.stringify(browserSessionIds().filter((id) => id !== sessionId)),
  );
}

export function fetchSessions(cursor?: string | null): Promise<SessionListResponse> {
  const params = new URLSearchParams({ limit: "20" });
  if (cursor) params.set("cursor", cursor);
  return apiGet<SessionListResponse>(`/api/v1/sessions?${params.toString()}`);
}

export function fetchSessionSnapshot(sessionId: string): Promise<SessionSnapshot> {
  return apiGet<SessionSnapshot>(
    `/api/v1/sessions/${encodeURIComponent(sessionId)}/snapshot`,
  );
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiDelete(`/api/v1/sessions/${encodeURIComponent(sessionId)}`);
  forgetBrowserSession(sessionId);
}

export function claimSessions(sessionIds: string[]): Promise<{ claimed: number }> {
  return apiPost<{ claimed: number }>("/api/v1/account/claim-sessions", {
    session_ids: sessionIds,
  });
}

export function fetchAccountPreferences(): Promise<AccountPreferencesResponse> {
  return apiGet<AccountPreferencesResponse>("/api/v1/account/preferences");
}

export function updateAccountPreferences(
  locale: AppLocale,
): Promise<{ locale: AppLocale }> {
  return apiPut<{ locale: AppLocale }>("/api/v1/account/preferences", { locale });
}
