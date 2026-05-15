"use client";

import { useChatStore } from "@/stores/chat-store";
import { SafetyReviewGate } from "./safety-review-gate";
import { BudgetReviewGate } from "./budget-review-gate";
import { HumanReviewGate } from "./human-review-gate";

export function HitlGateRenderer() {
  const interruptData = useChatStore((s) => s.interruptData);
  if (!interruptData) return null;

  switch (interruptData.gate) {
    case "safety_review":
      return <SafetyReviewGate data={interruptData} />;
    case "budget_review":
      return <BudgetReviewGate data={interruptData} />;
    case "human_review":
      return <HumanReviewGate data={interruptData} />;
    default:
      return (
        <div className="p-8 text-center text-muted-foreground">
          Unknown gate: {interruptData.gate}
        </div>
      );
  }
}
