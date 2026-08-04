"use client";

import { useLocale } from "next-intl";
import { localeTag, type AppLocale } from "@/i18n/config";
import type { DayWeather } from "@/lib/types";

function formatCalendarDate(value: string, locale: AppLocale): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return new Intl.DateTimeFormat(localeTag(locale), {
    day: "numeric",
    month: "short",
  }).format(date);
}

export function WeatherStrip({ days }: { days: DayWeather[] }) {
  const locale = useLocale() as AppLocale;
  const numberFormatter = new Intl.NumberFormat(localeTag(locale), {
    maximumFractionDigits: 0,
  });
  if (!days.length) return null;

  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {days.map((day) => (
        <div
          key={day.date}
          className="flex shrink-0 flex-col items-center gap-0.5 rounded-lg border bg-card px-3 py-2 text-center"
        >
          <span className="text-xs text-muted-foreground">
            {formatCalendarDate(day.date, locale)}
          </span>
          <span className="text-lg">{day.emoji}</span>
          <span className="text-xs font-medium">
            {numberFormatter.format(Math.round(day.temp_high_c))}° /{" "}
            {numberFormatter.format(Math.round(day.temp_low_c))}°
          </span>
          {day.rain_probability_pct > 30 && (
            <span className="text-[10px] text-blue-500">
              💧 {numberFormatter.format(day.rain_probability_pct)}%
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
