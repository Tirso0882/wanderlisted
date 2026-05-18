"use client";

import {
  Plane,
  Hotel,
  MapPin,
  Compass,
  Utensils,
  Bus,
  DollarSign,
  ClipboardList,
  LayoutGrid,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FlightCard } from "./flight-card";
import { HotelCard } from "./hotel-card";
import { PlaceCardComponent } from "./place-card";
import { TransportCard } from "./transport-card";
import { BudgetChart } from "./budget-chart";
import { DestinationTab } from "./destination-tab";
import { ItineraryTab } from "./itinerary-tab";
import { OverviewTab } from "./overview-tab";
import { useChatStore } from "@/stores/chat-store";
import type { AgentName, AgentStatus } from "@/lib/types";

const TAB_AGENT_MAP: Record<string, AgentName> = {
  flights: "FlightsAgent",
  hotels: "HotelsAgent",
  destination: "DestinationAgent",
  activities: "ActivitiesAgent",
  restaurants: "RestaurantsAgent",
  transport: "TransportationAgent",
  budget: "BudgetAgent",
  itinerary: "ItineraryAgent",
};

function TabDot({ status }: { status: AgentStatus }) {
  if (status === "idle") return null;
  const color =
    status === "completed"
      ? "bg-green-500"
      : status === "running"
        ? "bg-primary animate-pulse"
        : "bg-destructive";
  return <span className={`absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full ${color}`} />;
}

export function ResultsPanel() {
  const handbook = useChatStore((s) => s.handbook);
  const budget = useChatStore((s) => s.budget);
  const agents = useChatStore((s) => s.agents);
  const activeTab = useChatStore((s) => s.activeView);
  const setActiveTab = useChatStore((s) => s.setActiveView);

  // Extract data from handbook
  const flights = handbook?.flights ?? [];
  const hotels = handbook?.hotels ?? [];
  const days = handbook?.days ?? [];
  const safety = handbook?.safety ?? null;
  const culture = handbook?.culture ?? null;

  // Extract activities, restaurants, transport from day plans
  const allActivities = days.flatMap((d) =>
    d.time_blocks.flatMap((tb) => tb.activities),
  );
  const allRestaurants = days
    .flatMap((d) => d.time_blocks.map((tb) => tb.restaurant))
    .filter((r): r is NonNullable<typeof r> => r !== null);
  const allTransport = days.flatMap((d) =>
    d.time_blocks.flatMap((tb) => tb.transit),
  );

  const tabs = [
    { value: "overview", icon: LayoutGrid, label: "Overview" },
    { value: "flights", icon: Plane, label: "Flights" },
    { value: "hotels", icon: Hotel, label: "Hotels" },
    { value: "destination", icon: MapPin, label: "Destination" },
    { value: "activities", icon: Compass, label: "Activities" },
    { value: "restaurants", icon: Utensils, label: "Food" },
    { value: "transport", icon: Bus, label: "Transit" },
    { value: "budget", icon: DollarSign, label: "Budget" },
    { value: "itinerary", icon: ClipboardList, label: "Itinerary" },
  ];

  return (
    <Tabs
      value={activeTab}
      onValueChange={setActiveTab}
      className="flex h-full flex-col min-h-0"
    >
      <div className="border-b bg-background/50 px-4 pt-2 backdrop-blur-sm">
        <TabsList className="h-auto flex-wrap gap-1 bg-transparent p-0">
          {tabs.map((tab) => {
            const agentName = TAB_AGENT_MAP[tab.value];
            const status = agentName ? agents[agentName] : ("completed" as AgentStatus);
            const Icon = tab.icon;

            return (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="relative gap-1.5 rounded-lg px-3 py-2 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{tab.label}</span>
                <TabDot status={status} />
              </TabsTrigger>
            );
          })}
        </TabsList>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="mx-auto max-w-5xl p-4">
          <TabsContent value="overview" className="mt-0">
            <OverviewTab />
          </TabsContent>

          <TabsContent value="flights" className="mt-0">
            {flights.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2">
                {flights.map((f, i) => (
                  <FlightCard key={i} flight={f} />
                ))}
              </div>
            ) : (
              <EmptyTab label="flights" agentName="FlightsAgent" />
            )}
          </TabsContent>

          <TabsContent value="hotels" className="mt-0">
            {hotels.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2">
                {hotels.map((h, i) => (
                  <HotelCard key={i} hotel={h} />
                ))}
              </div>
            ) : (
              <EmptyTab label="hotels" agentName="HotelsAgent" />
            )}
          </TabsContent>

          <TabsContent value="destination" className="mt-0">
            <DestinationTab safety={safety} culture={culture} />
          </TabsContent>

          <TabsContent value="activities" className="mt-0">
            {allActivities.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {allActivities.map((a, i) => (
                  <PlaceCardComponent key={i} place={a} variant="activity" />
                ))}
              </div>
            ) : (
              <EmptyTab label="activities" agentName="ActivitiesAgent" />
            )}
          </TabsContent>

          <TabsContent value="restaurants" className="mt-0">
            {allRestaurants.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {allRestaurants.map((r, i) => (
                  <PlaceCardComponent key={i} place={r} variant="restaurant" />
                ))}
              </div>
            ) : (
              <EmptyTab label="restaurants" agentName="RestaurantsAgent" />
            )}
          </TabsContent>

          <TabsContent value="transport" className="mt-0">
            {allTransport.length > 0 ? (
              <div className="space-y-3">
                {allTransport.map((t, i) => (
                  <TransportCard key={i} step={t} />
                ))}
              </div>
            ) : (
              <EmptyTab label="transport options" agentName="TransportationAgent" />
            )}
          </TabsContent>

          <TabsContent value="budget" className="mt-0">
            {budget ? (
              <div className="mx-auto max-w-xl">
                <BudgetChart budget={budget} />
              </div>
            ) : (
              <EmptyTab label="budget breakdown" agentName="BudgetAgent" />
            )}
          </TabsContent>

          <TabsContent value="itinerary" className="mt-0">
            <ItineraryTab days={days} />
          </TabsContent>
        </div>
      </div>
    </Tabs>
  );
}

function EmptyTab({
  label,
  agentName,
}: {
  label: string;
  agentName: AgentName;
}) {
  const status = useChatStore((s) => s.agents[agentName]);

  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {status === "running" ? (
        <>
          <div className="mb-3 h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">
            Agent is working on {label}...
          </p>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">
          No {label} yet. They will appear here as the agents work.
        </p>
      )}
    </div>
  );
}
