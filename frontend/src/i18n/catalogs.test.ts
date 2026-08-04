import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import en from "../../messages/en.json";
import pl from "../../messages/pl.json";
import { resolveInitialLocale } from "./config";

function leafKeys(value: unknown, prefix = ""): string[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [prefix];
  return Object.entries(value).flatMap(([key, child]) =>
    leafKeys(child, prefix ? `${prefix}.${key}` : key),
  );
}

describe("bilingual catalogs", () => {
  it("keeps English and Polish keys identical", () => {
    expect(leafKeys(pl).sort()).toEqual(leafKeys(en).sort());
  });

  it("retains Polish diacritics and room for longer Polish UI copy", () => {
    expect(JSON.stringify(pl)).toMatch(/[ąćęłńóśźż]/i);
    expect(pl.welcome.privacy.length).toBeGreaterThan(en.welcome.privacy.length);
  });

  it("uses cookie, then Polish browser language, then English", () => {
    expect(resolveInitialLocale(undefined, "en", "pl-PL")).toBe("en");
    expect(resolveInitialLocale(undefined, undefined, "de-DE,pl;q=0.8")).toBe("pl");
    expect(resolveInitialLocale(undefined, undefined, "de-DE,en;q=0.8")).toBe("en");
  });

  it("prefers the saved account locale over cookie and browser language", () => {
    expect(resolveInitialLocale("pl", "en", "en-GB")).toBe("pl");
  });

  it("defines a reduced-motion override", () => {
    const css = readFileSync("src/app/globals.css", "utf8");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
  });
});
