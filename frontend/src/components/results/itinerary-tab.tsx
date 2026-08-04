"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertTriangle,
  Calendar,
  CircleAlert,
  Clock,
  ExternalLink,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { localeTag, type AppLocale } from "@/i18n/config";
import { formatCurrency } from "@/lib/format-currency";
import { WeatherStrip } from "./weather-strip";
import type {
  DayPlan,
  PlaceCard,
  TimeBlock,
  TransitStep,
} from "@/lib/types";

const PERIOD_LABELS = {
  morning: { label: "period.morning", emoji: "🌅" },
  afternoon: { label: "period.afternoon", emoji: "☀️" },
  evening: { label: "period.evening", emoji: "🌙" },
} as const satisfies Record<TimeBlock["period"], { label: string; emoji: string }>;

const TRANSPORT_LABELS = {
  walk: "transport.walk",
  transit: "transport.transit",
  drive: "transport.drive",
  train: "transport.train",
  bus: "transport.bus",
  ferry: "transport.ferry",
  bicycle: "transport.bicycle",
  subway: "transport.subway",
} as const satisfies Record<TransitStep["mode"], string>;

const FEASIBILITY_LABELS = {
  verified: "feasibility.verified",
  needs_review: "feasibility.needsReview",
  infeasible: "feasibility.infeasible",
} as const;

const COVERAGE_LABELS = {
  complete: "coverage.complete",
  partial: "coverage.partial",
  unavailable: "coverage.unavailable",
} as const;

function formatCalendarDate(value: string, locale: AppLocale): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return new Intl.DateTimeFormat(localeTag(locale), {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

function StopCard({
  place,
  label,
  unscheduled = false,
}: {
  place: PlaceCard;
  label?: string;
  unscheduled?: boolean;
}) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("itineraryDetails");
  const numberFormatter = new Intl.NumberFormat(localeTag(locale), {
    maximumFractionDigits: 1,
  });
  const scheduled =
    place.scheduled_start && place.scheduled_end
      ? `${place.scheduled_start}–${place.scheduled_end}`
      : "";

  return (
    <div className="flex gap-3 rounded-lg border bg-card p-3 transition-colors hover:bg-accent/50">
      {place.photo_urls?.[0] && (
        <img
          src={place.photo_urls[0]}
          alt={place.name}
          className="h-16 w-16 shrink-0 rounded-md object-cover"
          loading="lazy"
        />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            {label && (
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {label}
              </p>
            )}
            <p className="text-sm font-medium leading-tight">{place.name}</p>
          </div>
          <div className="flex items-center gap-2">
            {scheduled && (
              <Badge variant="outline" className="font-mono text-[11px]">
                {scheduled}
              </Badge>
            )}
            {place.estimated_cost_usd > 0 && !unscheduled && (
              <span className="shrink-0 text-xs font-semibold text-primary">
                {formatCurrency(place.estimated_cost_usd, "USD", {}, localeTag(locale))}
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">{place.category}</p>
        {place.description && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {place.description}
          </p>
        )}
        <div className="mt-1.5 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          {place.rating !== null && place.rating > 0 && (
            <span>⭐ {numberFormatter.format(place.rating)}</span>
          )}
          {place.estimated_duration_minutes > 0 && (
            <span className="flex items-center gap-0.5">
              <Clock className="h-3 w-3" />
              {t("minutes", { count: place.estimated_duration_minutes })}
            </span>
          )}
          {place.google_maps_url && (
            <a
              href={place.google_maps_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-0.5 text-primary hover:underline"
            >
              {t("map")} <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function TransitRow({ step }: { step: TransitStep }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("itineraryDetails");
  const scheduled =
    step.scheduled_start && step.scheduled_end
      ? `${step.scheduled_start}–${step.scheduled_end}`
      : "";

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
      {scheduled && <span className="font-mono">{scheduled}</span>}
      <span>{t(TRANSPORT_LABELS[step.mode])}</span>
      <span>•</span>
      <span className="min-w-0 flex-1 truncate">
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
          {formatCurrency(step.fare_estimate_usd, "USD", {}, localeTag(locale))}
        </span>
      )}
    </div>
  );
}

function TimeBlockCard({ block }: { block: TimeBlock }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("itineraryDetails");
  const period = PERIOD_LABELS[block.period];
  const timeline = [
    ...block.activities.map((place, index) => ({
      kind: "place" as const,
      place,
      label: undefined,
      key: place.source_id || `activity-${index}`,
      time: place.scheduled_start || "",
    })),
    ...(block.restaurant
      ? [
          {
            kind: "place" as const,
            place: block.restaurant,
            label: t("meal"),
            key: block.restaurant.source_id || "restaurant",
            time: block.restaurant.scheduled_start || "",
          },
        ]
      : []),
    ...block.transit.map((step, index) => ({
      kind: "transit" as const,
      step,
      key: `transit-${step.route_leg_index ?? index}`,
      time: step.scheduled_start || "",
    })),
  ].sort((left, right) => {
    if (!left.time || !right.time) return 0;
    return left.time.localeCompare(right.time);
  });

  return (
    <div className="space-y-2">
      <h4 className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <span>{period.emoji}</span>
        {t(period.label)}
        {block.start_time && block.end_time && (
          <span className="font-mono font-normal normal-case">
            {block.start_time}–{block.end_time}
          </span>
        )}
        {block.subtotal_usd > 0 && (
          <Badge variant="outline" className="ml-auto text-xs font-normal">
            {formatCurrency(block.subtotal_usd, "USD", {}, localeTag(locale))}
          </Badge>
        )}
      </h4>

      {timeline.map((entry) =>
        entry.kind === "place" ? (
          <StopCard
            key={entry.key}
            place={entry.place}
            label={entry.label}
          />
        ) : (
          <TransitRow key={entry.key} step={entry.step} />
        ),
      )}
    </div>
  );
}

const FEASIBILITY_STYLES = {
  verified:
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  needs_review:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  infeasible:
    "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
};

function DayCard({ day }: { day: DayPlan }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("itineraryDetails");
  const numberFormatter = new Intl.NumberFormat(localeTag(locale), {
    maximumFractionDigits: 1,
  });
  const [expanded, setExpanded] = useState(true);
  const warnings = day.feasibility_warnings ?? [];
  const assumptions = day.assumptions ?? [];
  const unscheduled = day.unscheduled_stops ?? [];

  return (
    <Card>
      <CardHeader className="pb-2">
        <button
          type="button"
          className="flex w-full items-start justify-between gap-3 text-left"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
            <Calendar className="h-4 w-4" />
            {t("dayTitle", { number: day.day_number, city: day.city })}
            <span className="font-normal text-muted-foreground">
              {formatCalendarDate(day.date, locale)}
            </span>
          </CardTitle>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {day.feasibility_status && (
              <Badge
                className={FEASIBILITY_STYLES[day.feasibility_status]}
              >
                {t(FEASIBILITY_LABELS[day.feasibility_status])}
              </Badge>
            )}
            {day.weather && (
              <span className="text-sm" title={day.weather.condition}>
                {day.weather.emoji} {numberFormatter.format(Math.round(day.weather.temp_high_c))}°/
                {numberFormatter.format(Math.round(day.weather.temp_low_c))}°
              </span>
            )}
            {day.daily_cost_usd > 0 && (
              <Badge variant="secondary" className="text-xs">
                {formatCurrency(day.daily_cost_usd, "USD", {}, localeTag(locale))}
              </Badge>
            )}
            <span className="text-xs text-muted-foreground">
              {expanded ? "▲" : "▼"}
            </span>
          </div>
        </button>
      </CardHeader>

      {expanded && (
        <CardContent className="space-y-4">
          {day.weather?.packing_tip && (
            <p className="rounded-md bg-blue-50 px-3 py-2 text-xs text-blue-700 dark:bg-blue-900/20 dark:text-blue-300">
              👕 {day.weather.packing_tip}
            </p>
          )}

          {warnings.length > 0 && (
            <div className="rounded-lg border border-amber-300/60 bg-amber-50 p-3 text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
              <div className="mb-1 flex items-center gap-2 text-xs font-semibold">
                <AlertTriangle className="h-4 w-4" />
                {t("reviewNeeded")}
              </div>
              <ul className="space-y-1 pl-5 text-xs">
                {warnings.map((warning) => (
                  <li key={warning} className="list-disc">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {day.time_blocks.map((block, index) => (
            <div key={`${block.period}-${index}`}>
              {index > 0 && <Separator className="my-3" />}
              <TimeBlockCard block={block} />
            </div>
          ))}

          {unscheduled.length > 0 && (
            <div className="space-y-2 rounded-lg border border-dashed border-red-300 p-3 dark:border-red-900">
              <div className="flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-300">
                <CircleAlert className="h-4 w-4" />
                {t("unscheduledTitle")}
              </div>
              <p className="text-xs text-muted-foreground">
                {t("unscheduledBody")}
              </p>
              {unscheduled.map((place, index) => (
                <StopCard
                  key={place.source_id || `unscheduled-${index}`}
                  place={place}
                  unscheduled
                />
              ))}
            </div>
          )}

          {day.route_map_url && (
            <div className="overflow-hidden rounded-lg border">
              <iframe
                src={day.route_map_url}
                width="100%"
                height="200"
                style={{ border: 0 }}
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
                title={t("routeMapTitle", { number: day.day_number })}
              />
            </div>
          )}

          <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
            {day.walking_km > 0 && (
              <span>🚶 {t("walkingDistance", { distance: numberFormatter.format(day.walking_km) })}</span>
            )}
            {day.cultural_tip && <span>💡 {day.cultural_tip}</span>}
            {day.cost_coverage && (
              <span className="capitalize">
                {t("costCoverage", { status: t(COVERAGE_LABELS[day.cost_coverage]) })}
              </span>
            )}
          </div>

          {assumptions.length > 0 && (
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer font-medium">{t("assumptions")}</summary>
              <ul className="mt-2 space-y-1 pl-5">
                {assumptions.map((assumption) => (
                  <li key={assumption} className="list-disc">
                    {assumption}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </CardContent>
      )}
    </Card>
  );
}

export function ItineraryTab({ days }: { days: DayPlan[] }) {
  const t = useTranslations("itineraryDetails");
  if (!days.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Calendar className="mb-3 h-8 w-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">
          {t("empty")}
        </p>
      </div>
    );
  }

  const weatherDays = days
    .map((day) => day.weather)
    .filter((weather): weather is NonNullable<typeof weather> => weather !== null);

  return (
    <div className="space-y-4">
      {weatherDays.length > 0 && <WeatherStrip days={weatherDays} />}
      {days.map((day) => (
        <DayCard key={day.day_number} day={day} />
      ))}
    </div>
  );
}
