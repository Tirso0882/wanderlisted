"use client";

import type { DayWeather } from "@/lib/types";

export function WeatherStrip({ days }: { days: DayWeather[] }) {
  if (!days.length) return null;

  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {days.map((day) => (
        <div
          key={day.date}
          className="flex shrink-0 flex-col items-center gap-0.5 rounded-lg border bg-card px-3 py-2 text-center"
        >
          <span className="text-xs text-muted-foreground">{day.date}</span>
          <span className="text-lg">{day.emoji}</span>
          <span className="text-xs font-medium">
            {Math.round(day.temp_high_c)}° / {Math.round(day.temp_low_c)}°
          </span>
          {day.rain_probability_pct > 30 && (
            <span className="text-[10px] text-blue-500">
              💧 {day.rain_probability_pct}%
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
