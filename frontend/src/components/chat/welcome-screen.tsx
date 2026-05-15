"use client";

import { Compass, MapPin, Plane, Utensils } from "lucide-react";
import { useChatStore } from "@/stores/chat-store";

const SUGGESTIONS = [
  {
    icon: Plane,
    text: "Plan a 7-day trip to Tokyo for 2, mid-range budget, in cherry blossom season",
  },
  {
    icon: MapPin,
    text: "Weekend getaway to Paris, luxury style, with restaurant recommendations",
  },
  {
    icon: Utensils,
    text: "10-day Italy food tour for a family of 4 on a budget",
  },
  {
    icon: Compass,
    text: "Adventure trip to New Zealand for 2 weeks, hiking and outdoor activities",
  },
];

export function WelcomeScreen() {
  const sendMessage = useChatStore((s) => s.sendMessage);

  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
        <Compass className="h-8 w-8 text-primary" />
      </div>

      <h1 className="mb-2 text-2xl font-semibold tracking-tight">
        Where to next?
      </h1>
      <p className="mb-8 max-w-md text-center text-muted-foreground">
        Describe your dream trip and I&apos;ll create a detailed itinerary with
        flights, hotels, activities, restaurants, and a day-by-day plan.
      </p>

      <div className="grid w-full max-w-2xl gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.text}
            onClick={() => sendMessage(s.text)}
            className="flex items-start gap-3 rounded-xl border bg-card p-4 text-left text-sm transition-colors hover:bg-accent"
          >
            <s.icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="text-muted-foreground">{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
