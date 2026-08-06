"use client";

import { Check, ListPlus } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import type { AppLocale } from "@/i18n/config";
import type { RequestedCapability } from "@/lib/types";
import { useChatStore } from "@/stores/chat-store";

export function ServiceScopeCard() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("serviceScope");
  const offer = useChatStore((state) => state.components?.service_scope_offer);
  const isStreaming = useChatStore((state) => state.isStreaming);
  const sendMessage = useChatStore((state) => state.sendMessage);
  const [selection, setSelection] = useState<{
    fingerprint: string;
    capabilities: RequestedCapability[];
  }>({ fingerprint: "", capabilities: [] });

  if (!offer) return null;
  const selected =
    selection.fingerprint === offer.request_fingerprint
      ? selection.capabilities
      : [];

  const submit = (action: "include_all" | "include_selected" | "selected_only") => {
    const decision =
      action === "include_selected"
        ? {
            action,
            selected_capabilities: selected,
            request_fingerprint: offer.request_fingerprint,
          }
        : { action, request_fingerprint: offer.request_fingerprint };
    sendMessage(t(`messages.${action}`), locale, decision);
  };

  return (
    <section
      className="atlas-gate-card atlas-service-scope"
      aria-labelledby="service-scope-title"
      aria-live="polite"
    >
      <div className="atlas-gate-eyebrow">{t("eyebrow")}</div>
      <div className="atlas-gate-title-row">
        <ListPlus className="h-5 w-5 text-[var(--atlas-coral)]" aria-hidden="true" />
        <h3 id="service-scope-title">{t("title")}</h3>
      </div>
      <p className="atlas-gate-summary">{t("body")}</p>
      <div className="atlas-service-options">
        {offer.offered_capabilities.map((capability) => {
          const checked = selected.includes(capability);
          return (
            <label key={capability} className="atlas-service-option">
              <input
                type="checkbox"
                checked={checked}
                disabled={isStreaming}
                onChange={() =>
                  setSelection({
                    fingerprint: offer.request_fingerprint,
                    capabilities: checked
                      ? selected.filter((item) => item !== capability)
                      : [...selected, capability],
                  })
                }
              />
              <span>{t(`services.${capability}`)}</span>
            </label>
          );
        })}
      </div>
      <div className="atlas-gate-actions">
        <button
          type="button"
          className="atlas-primary-button"
          disabled={isStreaming || selected.length === 0}
          onClick={() => submit("include_selected")}
        >
          <Check className="h-4 w-4" aria-hidden="true" /> {t("addSelected")}
        </button>
        <button
          type="button"
          className="atlas-secondary-button"
          disabled={isStreaming}
          onClick={() => submit("include_all")}
        >
          {t("addAll")}
        </button>
        <button
          type="button"
          className="atlas-secondary-button"
          disabled={isStreaming}
          onClick={() => submit("selected_only")}
        >
          {t("currentOnly")}
        </button>
      </div>
    </section>
  );
}
