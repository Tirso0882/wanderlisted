"use client";

import { useEffect, useState } from "react";
import { ChatPanel } from "@/components/chat/chat-panel";
import { AgentActivityBar } from "@/components/chat/agent-activity-bar";
import { ResultsPanel } from "@/components/results/results-panel";
import { TripHeader } from "@/components/layout/trip-header";
import { HitlGateRenderer } from "@/components/hitl/hitl-gate-renderer";
import { ChatInput } from "@/components/chat/chat-input";
import { useChatStore } from "@/stores/chat-store";
import { MessageSquare, X, ChevronDown } from "lucide-react";

export default function ChatPage() {
  const interruptData = useChatStore((s) => s.interruptData);
  const handbook = useChatStore((s) => s.handbook);
  const loadMockData = useChatStore((s) => s.loadMockData);
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const [chatOpen, setChatOpen] = useState(false);

  // Auto-load mock data on mount if no handbook loaded
  useEffect(() => {
    if (!handbook) {
      loadMockData();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-open chat when streaming starts
  useEffect(() => {
    if (isStreaming) setChatOpen(true);
  }, [isStreaming]);

  const hasHandbook = handbook !== null;

  if (!hasHandbook) {
    // Show chat-first view while no data is ready
    return (
      <div className="flex flex-1 flex-col overflow-hidden">
        <AgentActivityBar />
        {interruptData ? <HitlGateRenderer /> : <ChatPanel />}
      </div>
    );
  }

  // Tab-centric view when data is available
  return (
    <div className="flex flex-1 flex-col overflow-hidden min-h-0">
      <TripHeader />
      <div className="flex-1 overflow-hidden min-h-0">
        <ResultsPanel />
      </div>

      {/* Floating chat drawer */}
      <div className="border-t bg-background">
        {chatOpen ? (
          <div className="flex flex-col" style={{ height: "320px" }}>
            <div className="flex items-center justify-between border-b px-4 py-2">
              <span className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Chat
                {messages.length > 0 && (
                  <span className="text-xs text-muted-foreground/60">
                    ({messages.length} messages)
                  </span>
                )}
              </span>
              <button
                onClick={() => setChatOpen(false)}
                className="rounded-md p-1 hover:bg-muted"
                aria-label="Minimize chat"
              >
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>
            <ChatPanel />
          </div>
        ) : (
          <div className="px-4 py-3">
            <div className="mx-auto max-w-3xl flex items-center gap-2">
              <button
                onClick={() => setChatOpen(true)}
                className="shrink-0 rounded-md p-2 hover:bg-muted text-muted-foreground"
                aria-label="Open chat"
              >
                <MessageSquare className="h-5 w-5" />
              </button>
              <div className="flex-1">
                <ChatInput />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
