"use client";

import { useRef, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatInput } from "./chat-input";
import { MessageBubble } from "./message-bubble";
import { TypingIndicator } from "./typing-indicator";
import { WelcomeScreen } from "./welcome-screen";
import { useChatStore } from "@/stores/chat-store";

export function ChatPanel() {
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const streamingContent = useChatStore((s) => s.streamingContent);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages/tokens
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <ScrollArea className="flex-1 px-4">
        <div className="mx-auto max-w-3xl py-6">
          {!hasMessages && !isStreaming && <WelcomeScreen />}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* Active streaming content */}
          {isStreaming && streamingContent && (
            <MessageBubble
              message={{
                id: "streaming",
                role: "assistant",
                content: streamingContent,
                timestamp: Date.now(),
              }}
              isStreaming
            />
          )}

          {/* Typing indicator when streaming starts but no content yet */}
          {isStreaming && !streamingContent && <TypingIndicator />}

          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      <div className="border-t bg-background px-4 pb-4 pt-3">
        <div className="mx-auto max-w-3xl">
          <ChatInput />
        </div>
      </div>
    </div>
  );
}
