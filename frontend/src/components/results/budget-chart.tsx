"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatCurrency } from "@/lib/format-currency";
import type { BudgetAmounts, BudgetBreakdown, BudgetCategory } from "@/lib/types";
import { useLocale, useTranslations } from "next-intl";
import { localeTag, type AppLocale } from "@/i18n/config";

const COLORS = [
  "bg-blue-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-orange-500",
  "bg-purple-500",
  "bg-gray-400",
];

const BUDGET_LINES: BudgetCategory[] = [
  "flights",
  "accommodation",
  "transport",
  "meals",
  "activities",
  "misc",
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

export function BudgetChart({ budget }: { budget: BudgetBreakdown }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("results");
  const intlLocale = localeTag(locale);
  const amounts = budget.display_breakdown ?? baseAmounts(budget);
  const totalForPercent = amounts.total > 0 ? amounts.total : 1;
  const missing = (budget.missing_categories ?? []).map((category) => t(category)).join(", ");
  const estimated = (budget.estimated_categories ?? []).map((category) => t(category)).join(", ");
  const reserve =
    budget.display_reserve_recommendation ?? budget.reserve_recommendation ?? 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">{t("budget")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex h-4 w-full overflow-hidden rounded-full">
          {BUDGET_LINES.map((key, index) => {
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
          {BUDGET_LINES.map((key, index) => {
            const percentage = ((amounts[key] / totalForPercent) * 100).toFixed(0);
            return (
              <div key={key} className="flex items-center gap-2 text-xs">
                <div className={`h-2.5 w-2.5 rounded-full ${COLORS[index]}`} />
                <span className="text-muted-foreground">{t(key)}</span>
                <span className="ml-auto font-medium">
                  {formatCurrency(amounts[key], amounts.currency, {}, intlLocale)} ({percentage}%)
                </span>
              </div>
            );
          })}
        </div>

        <Separator />

        <div className="flex justify-between text-sm">
          <span className="font-semibold">{t("total")}</span>
          <span className="font-bold text-primary">
            {formatCurrency(amounts.total, amounts.currency, {}, intlLocale)}
          </span>
        </div>
        {amounts.per_person > 0 && (
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{t("perPerson")}</span>
            <span>{formatCurrency(amounts.per_person, amounts.currency, {}, intlLocale)}</span>
          </div>
        )}

        <div className="space-y-1 text-xs text-muted-foreground">
          <p>
            {t("coverage")}: {(budget.coverage_status ?? "partial").replaceAll("_", " ")}
          </p>
          {missing && <p className="text-destructive">{t("missing")}: {missing}</p>}
          {estimated && <p>{t("estimated")}: {estimated}</p>}
          {budget.contingency_included ? (
            <p>{t("total")} · {t("estimated")}</p>
          ) : reserve > 0 ? (
            <p>
              {t("reserveExcluded")}: {formatCurrency(reserve, amounts.currency, {}, intlLocale)}
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
