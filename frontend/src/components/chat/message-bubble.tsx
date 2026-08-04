"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { Check, Copy, Navigation2 } from "lucide-react";
import type { ChatMessage } from "@/stores/chat-store";
import { useTranslations } from "next-intl";
import { useState } from "react";

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const t = useTranslations();
  const [copied, setCopied] = useState(false);

  return (
    <div
      data-message-role={message.role}
      className={cn("atlas-message-row", isUser && "atlas-message-row-user")}
    >
      {!isUser && (
        <span className="atlas-assistant-avatar" aria-hidden="true">
          <Navigation2 className="h-4 w-4" />
        </span>
      )}
      <div className={cn("atlas-message-stack", isUser && "items-end")}>
        <span className="atlas-message-author">
          {isUser ? t("chat.you") : t("chat.assistant")}
        </span>
        <div
          className={cn(
            "atlas-message-bubble",
            isUser ? "atlas-message-user" : "atlas-message-assistant",
            isStreaming && "atlas-message-streaming",
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : message.content ? (
            <div className="prose prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          ) : null}
          {message.stopped && (
            <span className="atlas-stopped-label">{t("composer.stopped")}</span>
          )}
        </div>
        {!isUser && message.content && !isStreaming && (
          <button
            type="button"
            className="atlas-copy-button"
            aria-label={copied ? t("chat.copied") : t("chat.copy")}
            onClick={() => {
              void navigator.clipboard?.writeText(message.content);
              setCopied(true);
            }}
          >
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copied ? t("chat.copied") : t("chat.copy")}
          </button>
        )}
      </div>
    </div>
  );
}
