"use client";

import { useEffect, useRef } from "react";
import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { useAuthState } from "@/lib/auth-context";
import { isAppLocale } from "./config";

export function LocalePreferenceSync() {
  const locale = useLocale();
  const router = useRouter();
  const auth = useAuthState();
  const checked = useRef(false);

  useEffect(() => {
    if (!auth.enabled || !auth.isLoaded || !auth.isSignedIn || checked.current) return;
    checked.current = true;
    void (async () => {
      const response = await fetch("/api/v1/account/preferences", {
        cache: "no-store",
      }).catch(() => null);
      if (!response?.ok) return;
      const preference = (await response.json()) as { locale?: unknown };
      if (!isAppLocale(preference.locale)) return;
      const shouldRefresh = preference.locale !== locale;
      await fetch("/api/locale", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale: preference.locale }),
      });
      if (shouldRefresh) router.refresh();
    })();
  }, [auth.enabled, auth.isLoaded, auth.isSignedIn, locale, router]);

  return null;
}
