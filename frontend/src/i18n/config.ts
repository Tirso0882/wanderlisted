import en from "../../messages/en.json";
import pl from "../../messages/pl.json";

export const locales = ["en", "pl"] as const;
export type AppLocale = (typeof locales)[number];

export const messagesByLocale = { en, pl } as const;
export type AppMessages = typeof en;

export function isAppLocale(value: unknown): value is AppLocale {
  return value === "en" || value === "pl";
}

export function localeTag(locale: AppLocale): "en-GB" | "pl-PL" {
  return locale === "pl" ? "pl-PL" : "en-GB";
}

export function resolveInitialLocale(
  accountLocale: string | null | undefined,
  cookieLocale: string | null | undefined,
  acceptLanguage: string | null | undefined,
): AppLocale {
  if (isAppLocale(accountLocale)) return accountLocale;
  if (isAppLocale(cookieLocale)) return cookieLocale;
  const languages = (acceptLanguage ?? "")
    .split(",")
    .map((entry) => entry.split(";", 1)[0]?.trim().toLowerCase())
    .filter(Boolean);
  return languages.some(
    (language) => language === "pl" || language?.startsWith("pl-"),
  )
    ? "pl"
    : "en";
}
