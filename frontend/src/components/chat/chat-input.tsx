"use client";

import { useState, useRef, useCallback } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Send, Square } from "lucide-react";
import { useChatStore } from "@/stores/chat-store";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  variant?: "default" | "hero";
}

export function ChatInput({ variant = "default" }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const stopStreaming = useChatStore((s) => s.stopStreaming);
  const isStreaming = useChatStore((s) => s.isStreaming);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    sendMessage(trimmed);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [input, isStreaming, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  const isHero = variant === "hero";

  return (
    <div
      className={cn(
        "relative flex items-end gap-2",
        isHero && "rounded-2xl border bg-background shadow-lg p-2",
      )}
    >
      <Textarea
        ref={textareaRef}
        value={input}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder={
          isHero
            ? "Ask about flights, hotels, activities, or plan a full trip..."
            : "Ask a follow-up question..."
        }
        rows={isHero ? 2 : 1}
        className={cn(
          "resize-none pr-12",
          isHero
            ? "min-h-[60px] max-h-[200px] text-base border-0 shadow-none focus-visible:ring-0"
            : "min-h-[44px] max-h-[200px] text-sm",
        )}
        disabled={isStreaming}
        aria-label="Chat message input"
      />

      {isStreaming ? (
        <Button
          size="icon"
          variant="destructive"
          onClick={stopStreaming}
          className={cn(
            "absolute right-1.5 h-8 w-8",
            isHero ? "bottom-3 right-4 h-9 w-9" : "bottom-1.5",
          )}
          aria-label="Stop generating"
        >
          <Square className="h-4 w-4" />
        </Button>
      ) : (
        <Button
          size="icon"
          onClick={handleSubmit}
          disabled={!input.trim()}
          className={cn(
            "absolute right-1.5 h-8 w-8",
            isHero ? "bottom-3 right-4 h-9 w-9" : "bottom-1.5",
          )}
          aria-label="Send message"
        >
          <Send className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
