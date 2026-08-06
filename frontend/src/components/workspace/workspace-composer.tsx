"use client";

import { Send, Square } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useRef, useState } from "react";
import type { AppLocale } from "@/i18n/config";
import { useChatStore } from "@/stores/chat-store";
import { SuggestionChips } from "./suggestion-chips";
import { ServiceScopeCard } from "./service-scope-card";

export function WorkspaceComposer() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("composer");
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((state) => state.sendMessage);
  const stopStreaming = useChatStore((state) => state.stopStreaming);
  const isStreaming = useChatStore((state) => state.isStreaming);

  const submit = useCallback(() => {
    const message = input.trim();
    if (!message || isStreaming) return;
    sendMessage(message, locale);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [input, isStreaming, locale, sendMessage]);

  return (
    <div className="atlas-composer-wrap">
      <ServiceScopeCard />
      <SuggestionChips />
      <div className="atlas-composer">
        <textarea
          ref={textareaRef}
          value={input}
          rows={1}
          disabled={isStreaming}
          placeholder={t("placeholder")}
          aria-label={t("placeholder")}
          onChange={(event) => {
            setInput(event.target.value);
            event.currentTarget.style.height = "auto";
            event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 144)}px`;
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
        />
        {isStreaming ? (
          <button
            type="button"
            className="atlas-send atlas-stop"
            onClick={stopStreaming}
            aria-label={t("stop")}
          >
            <Square className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : (
          <button
            type="button"
            className="atlas-send"
            onClick={submit}
            disabled={!input.trim()}
            aria-label={t("send")}
          >
            <Send className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>
      <p className="atlas-composer-hint">{t("hint")}</p>
    </div>
  );
}
