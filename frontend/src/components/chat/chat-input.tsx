"use client";

import { useState, useRef, useCallback } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Send, Square } from "lucide-react";
import { useChatStore } from "@/stores/chat-store";

export function ChatInput() {
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
    // Reset textarea height
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

  // Auto-resize textarea
  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  return (
    <div className="relative flex items-end gap-2">
      <Textarea
        ref={textareaRef}
        value={input}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder="Plan your dream trip… (e.g., '10-day Japan trip for 2 in spring, mid-range budget')"
        rows={1}
        className="min-h-[44px] max-h-[200px] resize-none pr-12 text-sm"
        disabled={isStreaming}
        aria-label="Chat message input"
      />

      {isStreaming ? (
        <Button
          size="icon"
          variant="destructive"
          onClick={stopStreaming}
          className="absolute bottom-1.5 right-1.5 h-8 w-8"
          aria-label="Stop generating"
        >
          <Square className="h-4 w-4" />
        </Button>
      ) : (
        <Button
          size="icon"
          onClick={handleSubmit}
          disabled={!input.trim()}
          className="absolute bottom-1.5 right-1.5 h-8 w-8"
          aria-label="Send message"
        >
          <Send className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
