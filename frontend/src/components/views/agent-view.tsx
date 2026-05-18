"use client";

import { useRef, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Plane,
  Hotel,
  MapPin,
  Compass,
  Utensils,
  Bus,
  DollarSign,
  ClipboardList,
  Home,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageBubble } from "@/components/chat/message-bubble";
import { TypingIndicator } from "@/components/chat/typing-indicator";
import { AgentResultsPanel } from "@/components/views/agent-results-panel";
import { useChatStore, type ViewMode } from "@/stores/chat-store";
import type { AgentName } from "@/lib/types";
import { cn } from "@/lib/utils";

const VIEW_META: Record<
  Exclude<ViewMode, "home">,
  { icon: LucideIcon; label: string; color: string }
> = {
  flights: { icon: Plane, label: "Flights", color: "text-blue-500" },
  hotels: { icon: Hotel, label: "Hotels", color: "text-amber-500" },
  destination: { icon: MapPin, label: "Destination", color: "text-emerald-500" },
  activities: { icon: Compass, label: "Activities", color: "text-purple-500" },
  restaurants: { icon: Utensils, label: "Restaurants", color: "text-rose-500" },
  transport: { icon: Bus, label: "Transport", color: "text-teal-500" },
  budget: { icon: DollarSign, label: "Budget", color: "text-lime-600" },
  itinerary: { icon: ClipboardList, label: "Itinerary", color: "text-indigo-500" },
  "full-plan": { icon: ClipboardList, label: "Full Trip Plan", color: "text-primary" },
};

const VIEW_AGENT_MAP: Partial<Record<ViewMode, AgentName>> = {
  flights: "FlightsAgent",
  hotels: "HotelsAgent",
  destination: "DestinationAgent",
  activities: "ActivitiesAgent",
  restaurants: "RestaurantsAgent",
  transport: "TransportationAgent",
  budget: "BudgetAgent",
  itinerary: "ItineraryAgent",
};

export function AgentView() {
  const activeView = useChatStore((s) => s.activeView);
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const streamingContent = useChatStore((s) => s.streamingContent);
  const agents = useChatStore((s) => s.agents);
  const goHome = useChatStore((s) => s.goHome);
  const clearChat = useChatStore((s) => s.clearChat);
  const setActiveView = useChatStore((s) => s.setActiveView);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  if (activeView === "home") return null;

  const meta = VIEW_META[activeView];
  const Icon = meta.icon;
  const agentName = VIEW_AGENT_MAP[activeView];
  const agentStatus = agentName ? agents[agentName] : "idle";

  return (
    <div className="flex flex-1 flex-col min-h-0 overflow-hidden">
      {/* Top nav bar */}
      <div className="flex items-center justify-between border-b bg-background/80 backdrop-blur-sm px-4 py-2.5">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={goHome}
            className="h-8 w-8"
            aria-label="Back to home"
          >
            <Home className="h-4 w-4" />
          </Button>

          <div className="flex items-center gap-2">
            <Icon className={cn("h-5 w-5", meta.color)} />
            <h2 className="font-semibold text-sm">{meta.label}</h2>
            {agentStatus === "running" && (
              <motion.div
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
                className="h-2 w-2 rounded-full bg-primary"
              />
            )}
            {agentStatus === "completed" && (
              <span className="h-2 w-2 rounded-full bg-green-500" />
            )}
          </div>
        </div>

        {/* Nav pills for switching between agents */}
        <div className="hidden md:flex items-center gap-1">
          {Object.entries(VIEW_META).map(([key, m]) => {
            const NavIcon = m.icon;
            const isActive = key === activeView;
            return (
              <button
                key={key}
                onClick={() => setActiveView(key as ViewMode)}
                className={cn(
                  "flex items-center gap-1 rounded-full px-2.5 py-1 text-xs transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted",
                )}
              >
                <NavIcon className="h-3 w-3" />
                <span className="hidden lg:inline">{m.label}</span>
              </button>
            );
          })}
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={clearChat}
          className="h-8 w-8 text-muted-foreground"
          aria-label="Clear conversation"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Main content: split layout */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left: Chat */}
        <div className="flex flex-col w-full md:w-[400px] lg:w-[440px] border-r min-h-0">
          <ScrollArea className="flex-1">
            <div className="p-4 space-y-1">
              {messages.length === 0 && !isStreaming && (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Icon className={cn("h-10 w-10 mb-3", meta.color, "opacity-40")} />
                  <p className="text-sm text-muted-foreground max-w-[250px]">
                    Ask anything about {meta.label.toLowerCase()} — I&apos;ll find the best options for you.
                  </p>
                </div>
              )}

              {messages.map((msg) => (
                <MessageBubble key={msg.id} message={msg} />
              ))}

              {isStreaming && streamingContent && (
                <MessageBubble
                  message={{
                    id: "streaming",
                    role: "assistant",
                    content: streamingContent,
                    timestamp: 0,
                  }}
                  isStreaming
                />
              )}

              {isStreaming && !streamingContent && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>

          <div className="border-t p-3 bg-background">
            <ChatInput />
          </div>
        </div>

        {/* Right: Results panel */}
        <div className="hidden md:flex flex-1 flex-col min-h-0 bg-muted/30">
          <AgentResultsPanel view={activeView} />
        </div>
      </div>
    </div>
  );
}
