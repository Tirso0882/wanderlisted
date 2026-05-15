"use client";

import { ShieldAlert, ShieldCheck, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { resumeChat } from "@/lib/api/resume";
import { useChatStore } from "@/stores/chat-store";
import type { InterruptData } from "@/lib/types";

const ADVISORY_COLORS: Record<string, string> = {
  green: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  yellow: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  orange: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
  red: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
};

export function SafetyReviewGate({ data }: { data: InterruptData }) {
  const sessionId = useChatStore((s) => s.sessionId);
  const setInterruptData = useChatStore((s) => s.setInterruptData);

  const level = (data.advisory_level as string) ?? "orange";
  const summary = data.summary ?? "This destination has a travel advisory.";

  const handleDecision = async (approved: boolean) => {
    if (!sessionId) return;
    setInterruptData(null);
    await resumeChat({
      session_id: sessionId,
      decision: { approved, gate: "safety_review" },
    });
  };

  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-lg">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-6 w-6 text-orange-500" />
            <CardTitle>Safety Advisory</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Badge className={ADVISORY_COLORS[level] ?? ADVISORY_COLORS.orange}>
            Level: {level.toUpperCase()}
          </Badge>

          <p className="text-sm leading-relaxed text-muted-foreground">
            {summary}
          </p>

          <div className="flex gap-3 pt-2">
            <Button
              onClick={() => handleDecision(true)}
              className="flex-1 gap-2"
            >
              <ShieldCheck className="h-4 w-4" />
              Acknowledge &amp; Continue
            </Button>
            <Button
              variant="outline"
              onClick={() => handleDecision(false)}
              className="flex-1 gap-2"
            >
              <X className="h-4 w-4" />
              Cancel Trip
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
