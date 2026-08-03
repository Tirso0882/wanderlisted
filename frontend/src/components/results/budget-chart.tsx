"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatCurrency } from "@/lib/format-currency";
import type { BudgetAmounts, BudgetBreakdown, BudgetCategory } from "@/lib/types";

const COLORS = [
  "bg-blue-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-orange-500",
  "bg-purple-500",
  "bg-gray-400",
];

const BUDGET_LINES: { key: BudgetCategory; label: string }[] = [
  { key: "flights", label: "Flights" },
  { key: "accommodation", label: "Accommodation" },
  { key: "transport", label: "Transport" },
  { key: "meals", label: "Meals" },
  { key: "activities", label: "Activities" },
  { key: "misc", label: "Misc" },
];

function baseAmounts(budget: BudgetBreakdown): BudgetAmounts {
  return {
    flights: budget.flights,
    accommodation: budget.accommodation,
    transport: budget.transport,
    meals: budget.meals,
    activities: budget.activities,
    misc: budget.misc,
    total: budget.total,
    per_person: budget.per_person,
    target_budget: budget.target_budget ?? 0,
    remaining_budget: budget.remaining_budget ?? null,
    currency: budget.base_currency ?? budget.currency ?? "USD",
  };
}

function categoryList(categories: BudgetCategory[] | undefined): string {
  return (categories ?? []).map((category) => category.replaceAll("_", " ")).join(", ");
}

export function BudgetChart({ budget }: { budget: BudgetBreakdown }) {
  const amounts = budget.display_breakdown ?? baseAmounts(budget);
  const totalForPercent = amounts.total > 0 ? amounts.total : 1;
  const missing = categoryList(budget.missing_categories);
  const estimated = categoryList(budget.estimated_categories);
  const reserve =
    budget.display_reserve_recommendation ?? budget.reserve_recommendation ?? 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Budget Breakdown</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex h-4 w-full overflow-hidden rounded-full">
          {BUDGET_LINES.map(({ key }, index) => {
            const percentage = (amounts[key] / totalForPercent) * 100;
            if (percentage < 1) return null;
            return (
              <div
                key={key}
                className={`${COLORS[index]} transition-all`}
                style={{ width: `${percentage}%` }}
              />
            );
          })}
        </div>

        <div className="grid grid-cols-2 gap-2">
          {BUDGET_LINES.map(({ key, label }, index) => {
            const percentage = ((amounts[key] / totalForPercent) * 100).toFixed(0);
            return (
              <div key={key} className="flex items-center gap-2 text-xs">
                <div className={`h-2.5 w-2.5 rounded-full ${COLORS[index]}`} />
                <span className="text-muted-foreground">{label}</span>
                <span className="ml-auto font-medium">
                  {formatCurrency(amounts[key], amounts.currency)} ({percentage}%)
                </span>
              </div>
            );
          })}
        </div>

        <Separator />

        <div className="flex justify-between text-sm">
          <span className="font-semibold">Total</span>
          <span className="font-bold text-primary">
            {formatCurrency(amounts.total, amounts.currency)}
          </span>
        </div>
        {amounts.per_person > 0 && (
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Per person</span>
            <span>{formatCurrency(amounts.per_person, amounts.currency)}</span>
          </div>
        )}

        <div className="space-y-1 text-xs text-muted-foreground">
          <p>
            Coverage: {(budget.coverage_status ?? "partial").replaceAll("_", " ")}
          </p>
          {missing && <p className="text-destructive">Missing major costs: {missing}</p>}
          {estimated && <p>Estimated categories: {estimated}</p>}
          {budget.contingency_included ? (
            <p>Traveler contingency is included in the total.</p>
          ) : reserve > 0 ? (
            <p>
              Suggested reserve (excluded): {formatCurrency(reserve, amounts.currency)}
            </p>
          ) : null}
          {budget.assumptions?.slice(0, 4).map((assumption) => (
            <p key={assumption}>• {assumption}</p>
          ))}
        </div>

        {budget.summary && (
          <p className="text-xs text-muted-foreground">{budget.summary}</p>
        )}
      </CardContent>
    </Card>
  );
}
