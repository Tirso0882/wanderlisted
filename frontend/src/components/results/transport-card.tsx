"use client";

import { Bus, Train, Footprints, Car, Ship, Bike, ArrowRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { TransitStep } from "@/lib/types";
import type { LucideIcon } from "lucide-react";

const MODE_ICONS: Record<string, LucideIcon> = {
  walk: Footprints,
  transit: Train,
  drive: Car,
  train: Train,
  bus: Bus,
  ferry: Ship,
  bicycle: Bike,
  subway: Train,
};

export function TransportCard({ step }: { step: TransitStep }) {
  const Icon = MODE_ICONS[step.mode] ?? Bus;

  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
          <Icon className="h-4 w-4 text-muted-foreground" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-sm">
            <span className="truncate font-medium">{step.from_place}</span>
            <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="truncate font-medium">{step.to_place}</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {step.duration_text && <span>{step.duration_text}</span>}
            {step.distance_text && <span>· {step.distance_text}</span>}
            {step.transit_line && <span>· {step.transit_line}</span>}
          </div>
        </div>

        <div className="flex flex-col items-end gap-1">
          <Badge variant="secondary" className="text-xs capitalize">
            {step.mode}
          </Badge>
          {step.fare_estimate_usd > 0 && (
            <span className="text-xs font-medium text-primary">
              ${step.fare_estimate_usd}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
