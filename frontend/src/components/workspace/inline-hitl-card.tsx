"use client";

import {
  Check,
  CircleDollarSign,
  ClipboardCheck,
  Pencil,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import type { AppLocale } from "@/i18n/config";
import { resumeChat } from "@/lib/api/resume";
import type { BudgetAmounts, ResumeDecision } from "@/lib/types";
import { useChatStore } from "@/stores/chat-store";

export function InlineHitlCard() {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("gates");
  const interrupt = useChatStore((state) => state.interruptData);
  const sessionId = useChatStore((state) => state.sessionId);
  const budget = useChatStore((state) => state.budget);
  const applyResumeResponse = useChatStore((state) => state.applyResumeResponse);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [showTarget, setShowTarget] = useState(false);
  const [target, setTarget] = useState("");

  if (!interrupt) return null;

  const submit = async (decision: ResumeDecision) => {
    if (!sessionId || submitting) return;
    setSubmitting(true);
    setError(false);
    try {
      const response = await resumeChat({
        session_id: sessionId,
        decision,
        ui_locale: locale,
      });
      applyResumeResponse(response);
    } catch {
      setError(true);
    } finally {
      setSubmitting(false);
    }
  };

  const summary = typeof interrupt.summary === "string" ? interrupt.summary : "";
  const commonHeader = (
    <div className="atlas-gate-eyebrow">{t("inlineLabel")}</div>
  );

  if (interrupt.gate === "budget_review") {
    const display = (interrupt.display_breakdown as BudgetAmounts | undefined) ??
      budget?.display_breakdown;
    const currency = display?.currency ?? budget?.display_currency ?? "USD";
    const total = display?.total ?? budget?.total;
    const parsedTarget = Number(target);
    const validTarget = Number.isFinite(parsedTarget) && parsedTarget >= 0;
    return (
      <section className="atlas-gate-card" aria-labelledby="budget-gate-title">
        {commonHeader}
        <div className="atlas-gate-title-row">
          <CircleDollarSign className="h-5 w-5 text-[var(--atlas-teal-dark)]" />
          <h3 id="budget-gate-title">{t("budget.title")}</h3>
          {typeof total === "number" && (
            <span className="atlas-gate-badge">
              {new Intl.NumberFormat(locale === "pl" ? "pl-PL" : "en-GB", {
                style: "currency",
                currency,
              }).format(total)}
            </span>
          )}
        </div>
        {summary && <p className="atlas-gate-summary">{summary}</p>}
        {showTarget && (
          <label className="atlas-field-label">
            {t("budget.newTarget", { currency })}
            <input
              type="number"
              min="0"
              step="0.01"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
            />
          </label>
        )}
        {error && <p className="atlas-form-error">{t("resumeError")}</p>}
        <div className="atlas-gate-actions">
          <button
            type="button"
            className="atlas-primary-button"
            disabled={submitting}
            onClick={() => void submit({ gate: "budget_review", action: "proceed" })}
          >
            <Check className="h-4 w-4" /> {t("budget.proceed")}
          </button>
          <button
            type="button"
            className="atlas-secondary-button"
            disabled={submitting || (showTarget && !validTarget)}
            onClick={() => {
              if (!showTarget) setShowTarget(true);
              else if (validTarget) {
                void submit({
                  gate: "budget_review",
                  action: "adjust_target",
                  new_budget: parsedTarget,
                });
              }
            }}
          >
            <Pencil className="h-4 w-4" />
            {showTarget ? t("budget.confirm") : t("budget.adjust")}
          </button>
          <button
            type="button"
            className="atlas-link-button"
            disabled={submitting}
            onClick={() => void submit({ gate: "budget_review", action: "cancel" })}
          >
            {t("budget.cancel")}
          </button>
        </div>
      </section>
    );
  }

  if (interrupt.gate === "human_review") {
    return (
      <section className="atlas-gate-card" aria-labelledby="human-gate-title">
        {commonHeader}
        <div className="atlas-gate-title-row">
          <ClipboardCheck className="h-5 w-5 text-[var(--atlas-teal-dark)]" />
          <h3 id="human-gate-title">{t("human.title")}</h3>
        </div>
        <p className="atlas-gate-summary">{summary || t("human.defaultBody")}</p>
        {showFeedback && (
          <label className="atlas-field-label">
            <span className="sr-only">{t("human.feedback")}</span>
            <textarea
              rows={3}
              value={feedback}
              placeholder={t("human.feedback")}
              onChange={(event) => setFeedback(event.target.value)}
            />
          </label>
        )}
        {error && <p className="atlas-form-error">{t("resumeError")}</p>}
        <div className="atlas-gate-actions">
          <button
            type="button"
            className="atlas-primary-button"
            disabled={submitting}
            onClick={() =>
              void submit({ gate: "human_review", action: "approved" })
            }
          >
            <Check className="h-4 w-4" /> {t("human.approve")}
          </button>
          <button
            type="button"
            className="atlas-secondary-button"
            disabled={submitting || (showFeedback && !feedback.trim())}
            onClick={() => {
              if (!showFeedback) setShowFeedback(true);
              else if (feedback.trim()) {
                void submit({
                  gate: "human_review",
                  action: "edited",
                  feedback: feedback.trim(),
                });
              }
            }}
          >
            <Pencil className="h-4 w-4" />
            {showFeedback ? t("human.submit") : t("human.request")}
          </button>
          <button
            type="button"
            className="atlas-link-button"
            disabled={submitting}
            onClick={() =>
              void submit({ gate: "human_review", action: "rejected" })
            }
          >
            {t("human.reject")}
          </button>
        </div>
      </section>
    );
  }

  return <p className="atlas-form-error">{t("unknown")}</p>;
}
