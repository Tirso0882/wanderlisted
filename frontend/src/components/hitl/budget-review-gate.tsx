"use client";

import { useState } from "react";
import { DollarSign, Check, Pencil, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { resumeChat } from "@/lib/api/resume";
import { useChatStore } from "@/stores/chat-store";
import type { InterruptData } from "@/lib/types";

interface BudgetLine {
  label: string;
  key: string;
}

const BUDGET_LINES: BudgetLine[] = [
  { label: "Flights", key: "flights" },
  { label: "Accommodation", key: "accommodation" },
  { label: "Transport", key: "transport" },
  { label: "Meals", key: "meals" },
  { label: "Activities", key: "activities" },
  { label: "Misc", key: "misc" },
];

export function BudgetReviewGate({ data }: { data: InterruptData }) {
  const sessionId = useChatStore((s) => s.sessionId);
  const budget = useChatStore((s) => s.budget);
  const setInterruptData = useChatStore((s) => s.setInterruptData);
  const [editing, setEditing] = useState(false);
  const [adjustedBudget, setAdjustedBudget] = useState("");

  const total = budget?.total ?? (data.estimated_total as number) ?? 0;
  const target = (data.target_budget as number) ?? 0;
  const delta = total - target;

  const handleDecision = async (action: "proceed" | "adjust" | "cancel") => {
    if (!sessionId) return;
    setInterruptData(null);
    await resumeChat({
      session_id: sessionId,
      decision: {
        gate: "budget_review",
        action,
        ...(action === "adjust" && adjustedBudget
          ? { new_budget: parseFloat(adjustedBudget) }
          : {}),
      },
    });
  };

  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-lg">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <DollarSign className="h-6 w-6 text-yellow-500" />
            <CardTitle>Budget Review</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{data.summary}</p>

          {/* Budget breakdown */}
          {budget && (
            <div className="space-y-2 rounded-lg bg-muted/50 p-3">
              {BUDGET_LINES.map(({ label, key }) => {
                const value = budget[key as keyof typeof budget];
                return (
                  <div
                    key={key}
                    className="flex justify-between text-sm"
                  >
                    <span className="text-muted-foreground">{label}</span>
                    <span className="font-medium">
                      ${typeof value === "number" ? value.toLocaleString() : 0}
                    </span>
                  </div>
                );
              })}
              <Separator />
              <div className="flex justify-between text-sm font-semibold">
                <span>Total</span>
                <span>${total.toLocaleString()}</span>
              </div>
              {delta > 0 && (
                <div className="flex justify-between text-sm text-destructive">
                  <span>Over target</span>
                  <span>+${delta.toLocaleString()}</span>
                </div>
              )}
            </div>
          )}

          {/* Adjust input */}
          {editing && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">New budget: $</span>
              <Input
                type="number"
                value={adjustedBudget}
                onChange={(e) => setAdjustedBudget(e.target.value)}
                placeholder={target.toString()}
                className="w-32"
              />
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <Button
              onClick={() => handleDecision("proceed")}
              className="flex-1 gap-2"
            >
              <Check className="h-4 w-4" />
              Proceed
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                if (editing) handleDecision("adjust");
                else setEditing(true);
              }}
              className="flex-1 gap-2"
            >
              <Pencil className="h-4 w-4" />
              {editing ? "Confirm Adjustment" : "Adjust Budget"}
            </Button>
            <Button
              variant="outline"
              onClick={() => handleDecision("cancel")}
              size="icon"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
