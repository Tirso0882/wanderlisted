"use client";

import { Plane, Clock, ArrowRight, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { FlightOption } from "@/lib/types";

export function FlightCard({ flight }: { flight: FlightOption }) {
  const outFirst = flight.outbound[0];
  const outLast = flight.outbound[flight.outbound.length - 1];
  const totalMinutes = flight.outbound.reduce(
    (sum, s) => sum + s.duration_minutes,
    0,
  );
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Plane className="h-4 w-4" />
            {outFirst?.carrier ?? "Airline"} {outFirst?.flight_number ?? ""}
          </CardTitle>
          <span className="text-lg font-bold text-primary">
            ${flight.total_price_usd.toLocaleString()}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Route */}
        <div className="flex items-center gap-3 text-sm">
          <div className="text-center">
            <p className="font-semibold">{outFirst?.departure_airport}</p>
            <p className="text-xs text-muted-foreground">
              {outFirst?.departure_time}
            </p>
          </div>
          <div className="flex flex-1 flex-col items-center">
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              {hours}h {mins}m
            </div>
            <div className="relative w-full">
              <div className="h-px bg-border" />
              <ArrowRight className="absolute right-0 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
            </div>
            {outFirst?.stops > 0 && (
              <p className="text-xs text-muted-foreground">
                {outFirst.stops} stop{outFirst.stops > 1 ? "s" : ""}
              </p>
            )}
          </div>
          <div className="text-center">
            <p className="font-semibold">{outLast?.arrival_airport}</p>
            <p className="text-xs text-muted-foreground">
              {outLast?.arrival_time}
            </p>
          </div>
        </div>

        {/* Cabin class + currency */}
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs capitalize">
            {outFirst?.cabin_class?.replace("_", " ") ?? "economy"}
          </Badge>
          <Badge variant="outline" className="text-xs">
            {flight.currency}
          </Badge>
        </div>

        {/* Booking links */}
        <div className="flex flex-wrap gap-2">
          {flight.booking_url && (
            <a
              href={flight.booking_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              Book <ExternalLink className="h-3 w-3" />
            </a>
          )}
          {flight.skyscanner_url && (
            <a
              href={flight.skyscanner_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"
            >
              Skyscanner <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
