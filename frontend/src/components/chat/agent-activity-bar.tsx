"use client";

import { motion } from "framer-motion";
import {
  Plane,
  Hotel,
  MapPin,
  Utensils,
  Compass,
  Bus,
  DollarSign,
  ClipboardList,
  type LucideIcon,
} from "lucide-react";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";
import type { AgentName, AgentStatus } from "@/lib/types";

const AGENT_META: Record<AgentName, { icon: LucideIcon; label: string; emoji: string }> = {
  FlightsAgent: { icon: Plane, label: "Flights", emoji: "✈️" },
  HotelsAgent: { icon: Hotel, label: "Hotels", emoji: "🏨" },
  DestinationAgent: { icon: MapPin, label: "Destination", emoji: "🗺️" },
  RestaurantsAgent: { icon: Utensils, label: "Restaurants", emoji: "🍽️" },
  ActivitiesAgent: { icon: Compass, label: "Activities", emoji: "🎯" },
  TransportationAgent: { icon: Bus, label: "Transport", emoji: "🚌" },
  BudgetAgent: { icon: DollarSign, label: "Budget", emoji: "💰" },
  ItineraryAgent: { icon: ClipboardList, label: "Itinerary", emoji: "📋" },
};

const STATUS_STYLES: Record<AgentStatus, string> = {
  idle: "bg-muted text-muted-foreground",
  running: "bg-primary/15 text-primary ring-2 ring-primary/30",
  completed: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  error: "bg-destructive/15 text-destructive",
};

export function AgentActivityBar() {
  const agents = useChatStore((s) => s.agents);
  const isStreaming = useChatStore((s) => s.isStreaming);

  // Only show when streaming or when agents have been activated
  const hasActivity = Object.values(agents).some((s) => s !== "idle");
  if (!hasActivity && !isStreaming) return null;

  return (
    <div className="flex items-center gap-1.5 overflow-x-auto border-b bg-background/50 px-4 py-2 backdrop-blur-sm">
      <span className="mr-2 text-xs font-medium text-muted-foreground whitespace-nowrap">
        Agents
      </span>
      {(Object.entries(agents) as [AgentName, AgentStatus][]).map(
        ([name, status]) => {
          const meta = AGENT_META[name];
          if (!meta) return null;
          const Icon = meta.icon;

          return (
            <Tooltip key={name}>
              <TooltipTrigger
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
                  STATUS_STYLES[status],
                )}
              >
                {status === "running" ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                  >
                    <Icon className="h-3.5 w-3.5" />
                  </motion.div>
                ) : (
                  <Icon className="h-3.5 w-3.5" />
                )}
                <span className="hidden sm:inline">{meta.label}</span>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p>
                  {meta.emoji} {meta.label}: {status}
                </p>
              </TooltipContent>
            </Tooltip>
          );
        },
      )}
    </div>
  );
}
