"use client";

import { Calendar, Sun, Cloud, MapPin, Clock, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { WeatherStrip } from "./weather-strip";
import type { DayPlan, TimeBlock } from "@/lib/types";
import { useState } from "react";

const PERIOD_LABELS: Record<string, { label: string; emoji: string }> = {
  morning: { label: "Morning", emoji: "🌅" },
  afternoon: { label: "Afternoon", emoji: "☀️" },
  evening: { label: "Evening", emoji: "🌙" },
};

function TimeBlockCard({ block }: { block: TimeBlock }) {
  const period = PERIOD_LABELS[block.period] ?? {
    label: block.period,
    emoji: "📍",
  };

  return (
    <div className="space-y-2">
      <h4 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <span>{period.emoji}</span>
        {period.label}
        {block.subtotal_usd > 0 && (
          <Badge variant="outline" className="ml-auto text-xs font-normal">
            ~${block.subtotal_usd}
          </Badge>
        )}
      </h4>

      {block.activities.map((activity, i) => (
        <div
          key={i}
          className="flex gap-3 rounded-lg border bg-card p-3 transition-colors hover:bg-accent/50"
        >
          {activity.photo_urls?.[0] && (
            <img
              src={activity.photo_urls[0]}
              alt={activity.name}
              className="h-16 w-16 shrink-0 rounded-md object-cover"
              loading="lazy"
            />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium leading-tight">
                {activity.name}
              </p>
              {activity.estimated_cost_usd > 0 && (
                <span className="shrink-0 text-xs font-semibold text-primary">
                  ${activity.estimated_cost_usd}
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground">{activity.category}</p>
            {activity.description && (
              <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                {activity.description}
              </p>
            )}
            <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
              {activity.rating !== null && activity.rating > 0 && (
                <span>⭐ {activity.rating.toFixed(1)}</span>
              )}
              {activity.estimated_duration_minutes > 0 && (
                <span className="flex items-center gap-0.5">
                  <Clock className="h-3 w-3" />
                  {activity.estimated_duration_minutes}m
                </span>
              )}
              {activity.google_maps_url && (
                <a
                  href={activity.google_maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-0.5 text-primary hover:underline"
                >
                  Map <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>
        </div>
      ))}

      {/* Transit steps */}
      {block.transit.map((step, i) => (
        <div
          key={`transit-${i}`}
          className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground"
        >
          <span className="capitalize">{step.mode}</span>
          <span>•</span>
          <span className="truncate">
            {step.from_place} → {step.to_place}
          </span>
          {step.duration_text && (
            <>
              <span>•</span>
              <span>{step.duration_text}</span>
            </>
          )}
          {step.fare_estimate_usd > 0 && (
            <span className="ml-auto font-medium">
              ${step.fare_estimate_usd}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

function DayCard({ day }: { day: DayPlan }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <Card>
      <CardHeader
        className="cursor-pointer pb-2"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Calendar className="h-4 w-4" />
            Day {day.day_number} — {day.city}
            <span className="font-normal text-muted-foreground">
              {day.date}
            </span>
          </CardTitle>
          <div className="flex items-center gap-2">
            {day.weather && (
              <span className="text-sm" title={day.weather.condition}>
                {day.weather.emoji}{" "}
                {Math.round(day.weather.temp_high_c)}°/
                {Math.round(day.weather.temp_low_c)}°
              </span>
            )}
            {day.daily_cost_usd > 0 && (
              <Badge variant="secondary" className="text-xs">
                ${day.daily_cost_usd}
              </Badge>
            )}
            <span className="text-xs text-muted-foreground">
              {expanded ? "▲" : "▼"}
            </span>
          </div>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="space-y-4">
          {day.weather?.packing_tip && (
            <p className="rounded-md bg-blue-50 px-3 py-2 text-xs text-blue-700 dark:bg-blue-900/20 dark:text-blue-300">
              👕 {day.weather.packing_tip}
            </p>
          )}

          {day.time_blocks.map((block, i) => (
            <div key={i}>
              {i > 0 && <Separator className="my-3" />}
              <TimeBlockCard block={block} />
            </div>
          ))}

          {day.route_map_url && (
            <div className="overflow-hidden rounded-lg border">
              <iframe
                src={day.route_map_url}
                width="100%"
                height="200"
                style={{ border: 0 }}
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                title={`Day ${day.day_number} route map`}
              />
            </div>
          )}

          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            {day.walking_km > 0 && <span>🚶 {day.walking_km} km walking</span>}
            {day.cultural_tip && <span>💡 {day.cultural_tip}</span>}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

export function ItineraryTab({ days }: { days: DayPlan[] }) {
  if (!days.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Calendar className="mb-3 h-8 w-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">
          Your day-by-day itinerary will appear here once assembled.
        </p>
      </div>
    );
  }

  // Collect all weather data
  const weatherDays = days
    .map((d) => d.weather)
    .filter((w): w is NonNullable<typeof w> => w !== null);

  return (
    <div className="space-y-4">
      {weatherDays.length > 0 && <WeatherStrip days={weatherDays} />}
      {days.map((day) => (
        <DayCard key={day.day_number} day={day} />
      ))}
    </div>
  );
}
