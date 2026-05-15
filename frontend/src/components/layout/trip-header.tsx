"use client";

import { Calendar, MapPin, Users, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useChatStore } from "@/stores/chat-store";

export function TripHeader() {
  const handbook = useChatStore((s) => s.handbook);

  if (!handbook) return null;

  const startDate = handbook.start_date
    ? new Date(handbook.start_date).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      })
    : null;
  const endDate = handbook.end_date
    ? new Date(handbook.end_date).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : null;

  return (
    <div
      className="border-b px-6 py-4"
      style={{
        background: handbook.hero_gradient_from
          ? `linear-gradient(135deg, ${handbook.hero_gradient_from}15, ${handbook.hero_gradient_to}10)`
          : undefined,
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-lg font-semibold leading-tight tracking-tight">
            {handbook.hero_emoji && (
              <span className="mr-2">{handbook.hero_emoji}</span>
            )}
            {handbook.trip_title || "Your Trip"}
          </h1>

          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            {handbook.destinations.length > 0 && (
              <span className="flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {handbook.route_cities?.join(" → ") ||
                  handbook.destinations.join(", ")}
              </span>
            )}
            {startDate && endDate && (
              <span className="flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5" />
                {startDate} – {endDate}
              </span>
            )}
            {handbook.group_type && (
              <span className="flex items-center gap-1">
                <Users className="h-3.5 w-3.5" />
                <span className="capitalize">
                  {handbook.group_type.replace("_", " ")}
                </span>
              </span>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {handbook.travel_style && (
            <Badge variant="secondary" className="capitalize">
              <Sparkles className="mr-1 h-3 w-3" />
              {handbook.travel_style.replace("_", " ")}
            </Badge>
          )}
          {handbook.season && (
            <Badge variant="outline" className="capitalize">
              {handbook.season}
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
}
