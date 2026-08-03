"use client";

import { useState } from "react";
import { CircleDollarSign, Check, Pencil, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { formatCurrency } from "@/lib/format-currency";
import { resumeChat } from "@/lib/api/resume";
import { useChatStore } from "@/stores/chat-store";
import type {
  BudgetAmounts,
  BudgetCategory,
  InterruptData,
  ResumeDecision,
} from "@/lib/types";

const BUDGET_LINES: { label: string; key: BudgetCategory }[] = [
  { label: "Flights", key: "flights" },
  { label: "Accommodation", key: "accommodation" },
  { label: "Transport", key: "transport" },
  { label: "Meals", key: "meals" },
  { label: "Activities", key: "activities" },
  { label: "Misc", key: "misc" },
];

export function BudgetReviewGate({ data }: { data: InterruptData }) {
  const sessionId = useChatStore((state) => state.sessionId);
  const budget = useChatStore((state) => state.budget);
  const setInterruptData = useChatStore((state) => state.setInterruptData);
  const setComponents = useChatStore((state) => state.setComponents);
  const setBudget = useChatStore((state) => state.setBudget);
  const [editing, setEditing] = useState(false);
  const [adjustedBudget, setAdjustedBudget] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const interruptDisplay = (data.display_breakdown as BudgetAmounts | null) ?? null;
  const amounts = budget?.display_breakdown ?? interruptDisplay;
  const currency =
    amounts?.currency ?? budget?.base_currency ?? (data.currency as string) ?? "USD";
  const total = amounts?.total ?? budget?.total ?? (data.estimated_total as number) ?? 0;
  const target =
    amounts?.target_budget ?? budget?.target_budget ?? (data.target_budget as number) ?? 0;
  const overage = Math.max(0, total - target);
  const parsedAdjustment = Number(adjustedBudget);
  const validAdjustment = Number.isFinite(parsedAdjustment) && parsedAdjustment >= 0;

  const handleDecision = async (decision: ResumeDecision) => {
    if (!sessionId || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const result = await resumeChat({ session_id: sessionId, decision });
      setComponents(result.components);
      setBudget(result.budget);
      setInterruptData(result.interrupted ? result.interrupt_data : null);
    } catch (resumeError) {
      setError(
        resumeError instanceof Error
          ? resumeError.message
          : "Budget review could not be resumed.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-lg">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <CircleDollarSign className="h-6 w-6 text-yellow-500" />
            <CardTitle>Budget Review</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{data.summary}</p>

          {budget && (
            <div className="space-y-2 rounded-lg bg-muted/50 p-3">
              {BUDGET_LINES.map(({ label, key }) => (
                <div key={key} className="flex justify-between text-sm">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-medium">
                    {formatCurrency(amounts?.[key] ?? budget[key], currency)}
                  </span>
                </div>
              ))}
              <Separator />
              <div className="flex justify-between text-sm font-semibold">
                <span>Total</span>
                <span>{formatCurrency(total, currency)}</span>
              </div>
              {overage > 0 && (
                <div className="flex justify-between text-sm text-destructive">
                  <span>Over target</span>
                  <span>+{formatCurrency(overage, currency)}</span>
                </div>
              )}
              <div className="space-y-1 pt-1 text-xs text-muted-foreground">
                <p>
                  Coverage: {(budget.coverage_status ?? "partial").replaceAll("_", " ")}
                </p>
                {!!budget.missing_categories?.length && (
                  <p className="text-destructive">
                    Missing: {budget.missing_categories.join(", ")}
                  </p>
                )}
                {!!budget.estimated_categories?.length && (
                  <p>Estimated: {budget.estimated_categories.join(", ")}</p>
                )}
                {budget.contingency_included ? (
                  <p>Traveler contingency is included.</p>
                ) : budget.display_reserve_recommendation ? (
                  <p>
                    Reserve excluded: {formatCurrency(
                      budget.display_reserve_recommendation,
                      currency,
                    )}
                  </p>
                ) : null}
                {budget.assumptions?.slice(0, 3).map((assumption) => (
                  <p key={assumption}>• {assumption}</p>
                ))}
              </div>
            </div>
          )}

          {editing && (
            <div className="space-y-1">
              <label htmlFor="adjusted-budget" className="text-sm text-muted-foreground">
                New target ({currency})
              </label>
              <Input
                id="adjusted-budget"
                type="number"
                min="0"
                step="0.01"
                value={adjustedBudget}
                onChange={(event) => setAdjustedBudget(event.target.value)}
                placeholder={target.toString()}
                className="w-40"
              />
            </div>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex gap-3 pt-2">
            <Button
              onClick={() =>
                handleDecision({ gate: "budget_review", action: "proceed" })
              }
              disabled={submitting}
              className="flex-1 gap-2"
            >
              <Check className="h-4 w-4" />
              Proceed
            </Button>
            <Button
              variant="secondary"
              disabled={submitting || (editing && !validAdjustment)}
              onClick={() => {
                if (editing) {
                  handleDecision({
                    gate: "budget_review",
                    action: "adjust_target",
                    new_budget: parsedAdjustment,
                  });
                } else {
                  setEditing(true);
                }
              }}
              className="flex-1 gap-2"
            >
              <Pencil className="h-4 w-4" />
              {editing ? "Confirm Adjustment" : "Adjust Target"}
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                handleDecision({ gate: "budget_review", action: "cancel" })
              }
              disabled={submitting}
              size="icon"
              aria-label="Cancel trip"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
