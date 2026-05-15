"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { BudgetBreakdown } from "@/lib/types";

const COLORS = [
  "bg-blue-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-orange-500",
  "bg-purple-500",
  "bg-gray-400",
];

const LABELS = [
  "Flights",
  "Accommodation",
  "Transport",
  "Meals",
  "Activities",
  "Misc",
];

const KEYS: (keyof BudgetBreakdown)[] = [
  "flights",
  "accommodation",
  "transport",
  "meals",
  "activities",
  "misc",
];

export function BudgetChart({ budget }: { budget: BudgetBreakdown }) {
  const total = budget.total || 1; // Avoid division by zero

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Budget Breakdown</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Bar chart */}
        <div className="flex h-4 w-full overflow-hidden rounded-full">
          {KEYS.map((key, i) => {
            const value = budget[key] as number;
            const pct = (value / total) * 100;
            if (pct < 1) return null;
            return (
              <div
                key={key}
                className={`${COLORS[i]} transition-all`}
                style={{ width: `${pct}%` }}
              />
            );
          })}
        </div>

        {/* Legend */}
        <div className="grid grid-cols-2 gap-2">
          {KEYS.map((key, i) => {
            const value = budget[key] as number;
            const pct = ((value / total) * 100).toFixed(0);
            return (
              <div key={key} className="flex items-center gap-2 text-xs">
                <div className={`h-2.5 w-2.5 rounded-full ${COLORS[i]}`} />
                <span className="text-muted-foreground">{LABELS[i]}</span>
                <span className="ml-auto font-medium">
                  ${value.toLocaleString()} ({pct}%)
                </span>
              </div>
            );
          })}
        </div>

        <Separator />

        {/* Totals */}
        <div className="flex justify-between text-sm">
          <span className="font-semibold">Total</span>
          <span className="font-bold text-primary">
            ${budget.total.toLocaleString()} {budget.currency}
          </span>
        </div>
        {budget.per_person > 0 && (
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Per person</span>
            <span>${budget.per_person.toLocaleString()}</span>
          </div>
        )}
        {budget.summary && (
          <p className="text-xs text-muted-foreground">{budget.summary}</p>
        )}
      </CardContent>
    </Card>
  );
}
