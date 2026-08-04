"use client";

import { AlertTriangle, CheckCircle2, MapPin, Route, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";
import { MessageBubble } from "@/components/chat/message-bubble";
import { useChatStore } from "@/stores/chat-store";
import { InlineHitlCard } from "./inline-hitl-card";
import { TruthfulLoading } from "./truthful-loading";
import { WorkspaceComposer } from "./workspace-composer";

function WelcomeCanvas() {
  const t = useTranslations();
  return (
    <div className="atlas-welcome">
      <div className="atlas-welcome-orbit" aria-hidden="true">
        <span className="atlas-orbit-dot atlas-orbit-start" />
        <span className="atlas-orbit-dot atlas-orbit-end" />
        <Route className="atlas-orbit-plane" />
      </div>
      <p className="atlas-eyebrow">{t("welcome.eyebrow")}</p>
      <h1>{t("welcome.title")}</h1>
      <p className="atlas-welcome-body">{t("welcome.body")}</p>
      <div className="atlas-welcome-steps" aria-label={t("chat.welcomeRoute")}>
        <span><MapPin />{t("chat.welcomeStepOne")}</span>
        <span><ShieldCheck />{t("chat.welcomeStepTwo")}</span>
        <span><CheckCircle2 />{t("chat.welcomeStepThree")}</span>
      </div>
      <p className="atlas-privacy-note">{t("welcome.privacy")}</p>
    </div>
  );
}

export function WorkspaceChat() {
  const t = useTranslations();
  const messages = useChatStore((state) => state.messages);
  const isStreaming = useChatStore((state) => state.isStreaming);
  const streamingContent = useChatStore((state) => state.streamingContent);
  const errorKey = useChatStore((state) => state.errorKey);
  const setErrorKey = useChatStore((state) => state.setErrorKey);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    bottomRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
  }, [messages, streamingContent]);

  return (
    <section id="atlas-chat" className="atlas-chat-column" aria-label={t("a11y.conversation")}>
      <div className="atlas-pane-heading">
        <div>
          <p className="atlas-eyebrow">{t("brand.beta")}</p>
          <h2>{t("chat.title")}</h2>
        </div>
        <span>{t("chat.subtitle")}</span>
      </div>
      <div className="atlas-message-scroll" tabIndex={0}>
        <div className="atlas-message-list">
          {messages.length === 0 && !isStreaming && <WelcomeCanvas />}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {isStreaming && streamingContent && (
            <MessageBubble
              isStreaming
              message={{
                id: "streaming-response",
                role: "assistant",
                content: streamingContent,
                timestamp: 0,
              }}
            />
          )}
          {isStreaming && <TruthfulLoading />}
          <InlineHitlCard />
          {errorKey && (
            <div className="atlas-error-banner" role="alert">
              <AlertTriangle className="h-4 w-4" />
              <span>{t(`errors.${errorKey}`)}</span>
              <button type="button" onClick={() => setErrorKey(null)}>
                ×
              </button>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      <WorkspaceComposer />
    </section>
  );
}
