"use client";

import { useState } from "react";
import { ClipboardCheck, Check, Pencil, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { resumeChat } from "@/lib/api/resume";
import { useChatStore } from "@/stores/chat-store";
import type { InterruptData } from "@/lib/types";

export function HumanReviewGate({ data }: { data: InterruptData }) {
  const sessionId = useChatStore((s) => s.sessionId);
  const setInterruptData = useChatStore((s) => s.setInterruptData);
  const setComponents = useChatStore((s) => s.setComponents);
  const setBudget = useChatStore((s) => s.setBudget);
  const [feedback, setFeedback] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleDecision = async (action: "approved" | "edited" | "rejected") => {
    if (!sessionId || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const result = await resumeChat({
        session_id: sessionId,
        decision: {
          gate: "human_review",
          action,
          ...(feedback.trim() ? { feedback: feedback.trim() } : {}),
        },
      });
      setComponents(result.components);
      setBudget(result.budget);
      setInterruptData(result.interrupted ? result.interrupt_data : null);
    } catch (resumeError) {
      setError(
        resumeError instanceof Error
          ? resumeError.message
          : "Itinerary review could not be resumed.",
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
            <ClipboardCheck className="h-6 w-6 text-blue-500" />
            <CardTitle>Review Your Itinerary</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {data.summary ??
              "Your itinerary has been assembled. Review it and approve, request changes, or cancel."}
          </p>

          {showFeedback && (
            <Textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Describe the changes you'd like…"
              rows={3}
              className="text-sm"
            />
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex gap-3 pt-2">
            <Button
              onClick={() => handleDecision("approved")}
              disabled={submitting}
              className="flex-1 gap-2"
            >
              <Check className="h-4 w-4" />
              Approve
            </Button>
            <Button
              variant="secondary"
              disabled={submitting}
              onClick={() => {
                if (showFeedback && feedback.trim()) {
                  handleDecision("edited");
                } else {
                  setShowFeedback(true);
                }
              }}
              className="flex-1 gap-2"
            >
              <Pencil className="h-4 w-4" />
              {showFeedback ? "Submit Changes" : "Request Changes"}
            </Button>
            <Button
              variant="outline"
              onClick={() => handleDecision("rejected")}
              disabled={submitting}
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
