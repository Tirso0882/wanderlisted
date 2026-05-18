"use client";

import { motion } from "framer-motion";
import {
  Loader2,
  Plane,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FlightCard } from "@/components/results/flight-card";
import { HotelCard } from "@/components/results/hotel-card";
import { PlaceCardComponent } from "@/components/results/place-card";
import { TransportCard } from "@/components/results/transport-card";
import { BudgetChart } from "@/components/results/budget-chart";
import { DestinationTab } from "@/components/results/destination-tab";
import { ItineraryTab } from "@/components/results/itinerary-tab";
import { useChatStore, type ViewMode } from "@/stores/chat-store";
import type { AgentName } from "@/lib/types";

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

function EmptyState({ isLoading }: { isLoading: boolean }) {
  if (isLoading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-primary/50" />
        <p className="text-sm text-muted-foreground">Searching...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center px-6">
      <div className="h-12 w-12 rounded-xl bg-muted flex items-center justify-center">
        <Plane className="h-6 w-6 text-muted-foreground/50" />
      </div>
      <p className="text-sm text-muted-foreground max-w-[280px]">
        Results will appear here once the agent processes your request.
      </p>
    </div>
  );
}

export function AgentResultsPanel({ view }: { view: ViewMode }) {
  const handbook = useChatStore((s) => s.handbook);
  const budget = useChatStore((s) => s.budget);
  const agents = useChatStore((s) => s.agents);

  const agentName = VIEW_AGENT_MAP[view];
  const isLoading = agentName ? agents[agentName] === "running" : false;

  const flights = handbook?.flights ?? [];
  const hotels = handbook?.hotels ?? [];
  const days = handbook?.days ?? [];
  const safety = handbook?.safety ?? null;
  const culture = handbook?.culture ?? null;

  const allActivities = days.flatMap((d) =>
    d.time_blocks.flatMap((tb) => tb.activities),
  );
  const allRestaurants = days
    .flatMap((d) => d.time_blocks.map((tb) => tb.restaurant))
    .filter((r): r is NonNullable<typeof r> => r !== null);
  const allTransport = days.flatMap((d) =>
    d.time_blocks.flatMap((tb) => tb.transit),
  );

  const renderContent = () => {
    switch (view) {
      case "flights":
        if (flights.length === 0) return <EmptyState isLoading={isLoading} />;
        return (
          <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
            {flights.map((f, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <FlightCard flight={f} />
              </motion.div>
            ))}
          </div>
        );

      case "hotels":
        if (hotels.length === 0) return <EmptyState isLoading={isLoading} />;
        return (
          <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
            {hotels.map((h, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <HotelCard hotel={h} />
              </motion.div>
            ))}
          </div>
        );

      case "destination":
        if (!safety && !culture) return <EmptyState isLoading={isLoading} />;
        return <DestinationTab safety={safety} culture={culture} />;

      case "activities":
        if (allActivities.length === 0) return <EmptyState isLoading={isLoading} />;
        return (
          <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-3">
            {allActivities.map((a, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
              >
                <PlaceCardComponent place={a} variant="activity" />
              </motion.div>
            ))}
          </div>
        );

      case "restaurants":
        if (allRestaurants.length === 0) return <EmptyState isLoading={isLoading} />;
        return (
          <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-3">
            {allRestaurants.map((r, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
              >
                <PlaceCardComponent place={r} variant="restaurant" />
              </motion.div>
            ))}
          </div>
        );

      case "transport":
        if (allTransport.length === 0) return <EmptyState isLoading={isLoading} />;
        return (
          <div className="space-y-3">
            {allTransport.map((t, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
              >
                <TransportCard step={t} />
              </motion.div>
            ))}
          </div>
        );

      case "budget":
        if (!budget) return <EmptyState isLoading={isLoading} />;
        return (
          <div className="mx-auto max-w-xl">
            <BudgetChart budget={budget} />
          </div>
        );

      case "itinerary":
      case "full-plan":
        if (days.length === 0) return <EmptyState isLoading={isLoading} />;
        return <ItineraryTab days={days} />;

      default:
        return <EmptyState isLoading={isLoading} />;
    }
  };

  return (
    <ScrollArea className="flex-1">
      <div className="p-6">
        {renderContent()}
      </div>
    </ScrollArea>
  );
}
