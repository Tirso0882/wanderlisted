"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { AppLocale } from "@/i18n/config";
import { updateAccountPreferences } from "@/lib/api/sessions";
import { useAuthState } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";

export function LocaleSwitcher({ compact = false }: { compact?: boolean }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("locale");
  const auth = useAuthState();
  const router = useRouter();
  const setErrorKey = useChatStore((state) => state.setErrorKey);
  const [pending, setPending] = useState(false);

  const selectLocale = async (nextLocale: AppLocale) => {
    if (pending || nextLocale === locale) return;
    setPending(true);
    setErrorKey(null);
    try {
      if (auth.enabled && auth.isSignedIn) {
        await updateAccountPreferences(nextLocale);
      }
      const response = await fetch("/api/locale", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale: nextLocale }),
      });
      if (!response.ok) throw new Error("Locale cookie could not be updated");
      router.refresh();
    } catch {
      setErrorKey("preferences");
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border border-[var(--atlas-line)] bg-white/85 p-0.5 shadow-sm",
        compact ? "text-[0.68rem]" : "text-xs",
      )}
      role="group"
      aria-label={t("label")}
    >
      {(["en", "pl"] as const).map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={locale === option}
          aria-label={option === "en" ? t("switchToEnglish") : t("switchToPolish")}
          disabled={pending}
          onClick={() => void selectLocale(option)}
          className={cn(
            "rounded-full px-2.5 py-1 font-bold tracking-[0.08em] transition-colors",
            locale === option
              ? "bg-[var(--atlas-navy)] text-white"
              : "text-[var(--atlas-ink-soft)] hover:text-[var(--atlas-navy)]",
          )}
        >
          {option.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
