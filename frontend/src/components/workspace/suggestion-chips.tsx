"use client";

import { ArrowUpRight } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { AppLocale } from "@/i18n/config";
import { useChatStore } from "@/stores/chat-store";

const SUGGESTION_KEYS = {
  start: ["startOne", "startTwo", "startThree"],
  active: ["activeOne", "activeTwo", "activeThree"],
  results: ["resultsOne", "resultsTwo", "resultsThree"],
} as const;

export function SuggestionChips() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("composer");
  const messages = useChatStore((state) => state.messages);
  const components = useChatStore((state) => state.components);
  const isStreaming = useChatStore((state) => state.isStreaming);
  const sendMessage = useChatStore((state) => state.sendMessage);
  const phase = messages.length === 0 ? "start" : components ? "results" : "active";

  return (
    <div aria-label={t("suggestionLabel")} className="atlas-suggestion-row">
      {SUGGESTION_KEYS[phase].map((key) => {
        const label = t(`suggestions.${key}`);
        return (
          <button
            key={key}
            type="button"
            disabled={isStreaming}
            onClick={() => sendMessage(label, locale)}
            className="atlas-suggestion-chip"
          >
            <span>{label}</span>
            <ArrowUpRight className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}
