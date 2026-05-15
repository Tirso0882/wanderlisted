"use client";

import {
  Plane,
  Hotel,
  MapPin,
  Utensils,
  Compass,
  Bus,
  DollarSign,
  ClipboardList,
  CheckCircle2,
  Loader2,
  Circle,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useChatStore } from "@/stores/chat-store";
import type { AgentName, AgentStatus } from "@/lib/types";
import type { LucideIcon } from "lucide-react";

const AGENT_META: {
  name: AgentName;
  icon: LucideIcon;
  label: string;
  tab: string;
  description: string;
}[] = [
  {
    name: "FlightsAgent",
    icon: Plane,
    label: "Flights",
    tab: "flights",
    description: "Searching flights and comparing prices",
  },
  {
    name: "HotelsAgent",
    icon: Hotel,
    label: "Hotels",
    tab: "hotels",
    description: "Finding accommodations and availability",
  },
  {
    name: "DestinationAgent",
    icon: MapPin,
    label: "Destination",
    tab: "destination",
    description: "Researching safety, culture, and local info",
  },
  {
    name: "ActivitiesAgent",
    icon: Compass,
    label: "Activities",
    tab: "activities",
    description: "Discovering things to do and attractions",
  },
  {
    name: "RestaurantsAgent",
    icon: Utensils,
    label: "Restaurants",
    tab: "restaurants",
    description: "Finding dining options and food experiences",
  },
  {
    name: "TransportationAgent",
    icon: Bus,
    label: "Transportation",
    tab: "transport",
    description: "Planning local transit and routes",
  },
  {
    name: "BudgetAgent",
    icon: DollarSign,
    label: "Budget",
    tab: "budget",
    description: "Calculating costs and budget breakdown",
  },
  {
    name: "ItineraryAgent",
    icon: ClipboardList,
    label: "Itinerary",
    tab: "itinerary",
    description: "Assembling your day-by-day plan",
  },
];

const STATUS_ICON: Record<AgentStatus, LucideIcon> = {
  idle: Circle,
  running: Loader2,
  completed: CheckCircle2,
  error: Circle,
};

const STATUS_STYLE: Record<AgentStatus, string> = {
  idle: "text-muted-foreground/40",
  running: "text-primary animate-spin",
  completed: "text-green-500",
  error: "text-destructive",
};

export function OverviewTab() {
  const agents = useChatStore((s) => s.agents);
  const setActiveTab = useChatStore((s) => s.setActiveTab);
  const handbook = useChatStore((s) => s.handbook);

  const completedCount = Object.values(agents).filter(
    (s) => s === "completed",
  ).length;
  const totalAgents = Object.keys(agents).length;

  return (
    <div className="space-y-6">
      {/* Progress summary */}
      <div className="flex items-center gap-4">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{
              width: `${(completedCount / totalAgents) * 100}%`,
            }}
          />
        </div>
        <span className="text-sm font-medium text-muted-foreground">
          {completedCount}/{totalAgents} agents
        </span>
      </div>

      {/* Agent grid */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {AGENT_META.map((agent) => {
          const status = agents[agent.name];
          const StatusIcon = STATUS_ICON[status];
          const isClickable = status === "completed";

          return (
            <Card
              key={agent.name}
              className={`transition-all ${
                isClickable
                  ? "cursor-pointer hover:border-primary/50 hover:shadow-md"
                  : "opacity-60"
              }`}
              onClick={() => {
                if (isClickable) setActiveTab(agent.tab);
              }}
            >
              <CardContent className="flex items-start gap-3 p-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <agent.icon className="h-5 w-5 text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">{agent.label}</p>
                    <StatusIcon
                      className={`h-4 w-4 ${STATUS_STYLE[status]}`}
                    />
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {status === "completed"
                      ? "Click to view results"
                      : status === "running"
                        ? agent.description
                        : "Waiting to start"}
                  </p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Trip summary stats */}
      {handbook && (
        <div className="grid gap-3 sm:grid-cols-3">
          {handbook.days.length > 0 && (
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold">{handbook.days.length}</p>
                <p className="text-xs text-muted-foreground">Days planned</p>
              </CardContent>
            </Card>
          )}
          {handbook.hotels.length > 0 && (
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold">{handbook.hotels.length}</p>
                <p className="text-xs text-muted-foreground">
                  Hotel options found
                </p>
              </CardContent>
            </Card>
          )}
          {handbook.budget_total > 0 && (
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold">
                  ${handbook.budget_total.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">Est. total cost</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
