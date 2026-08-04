"use client";

import { AlertCircle, CalendarDays, ExternalLink, Route, Users } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { AppLocale } from "@/i18n/config";
import { ResultsPanel } from "@/components/results/results-panel";
import type {
  AgentName,
  ComponentOutcomeStatus,
  TravelReadinessReport,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";

const COMPONENT_LABELS: Record<string, AgentName> = {
  flights: "FlightsAgent",
  hotels: "HotelsAgent",
  hotel_stays: "HotelsAgent",
  readiness: "TravelReadinessAgent",
  readiness_preflight: "TravelReadinessAgent",
  restaurants: "RestaurantsAgent",
  activities: "ActivitiesAgent",
  transportation: "TransportationAgent",
  budget: "BudgetAgent",
  itinerary: "ItineraryAgent",
};

const STATUS_LABELS = {
  queued: "queued",
  running: "running",
  completed: "completed",
  partial: "partial",
  needs_user_input: "needsInput",
  no_inventory: "noInventory",
  blocked_external: "external",
  failed: "failed",
  stale: "stale",
} as const satisfies Record<ComponentOutcomeStatus, string>;

function statusTone(status: ComponentOutcomeStatus): string {
  if (status === "completed") return "atlas-outcome-complete";
  if (status === "partial" || status === "needs_user_input") return "atlas-outcome-partial";
  if (status === "queued" || status === "running") return "atlas-outcome-running";
  return "atlas-outcome-blocked";
}

export function TripWorkspacePanel({ consultationUrl }: { consultationUrl?: string }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations();
  const agentsT = useTranslations("agents");
  const resultsT = useTranslations("results");
  const handbook = useChatStore((state) => state.handbook);
  const budget = useChatStore((state) => state.budget);
  const components = useChatStore((state) => state.components);
  const outcomes = Object.entries(components?.component_results ?? {});
  const readiness =
    (components?.readiness as { data?: TravelReadinessReport } | undefined)?.data ??
    (components?.readiness_preflight as { data?: TravelReadinessReport } | undefined)?.data;
  const hasResults = Boolean(handbook || budget || outcomes.length || readiness);
  const dateFormatter = new Intl.DateTimeFormat(locale === "pl" ? "pl-PL" : "en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return (
    <section className="atlas-trip-column" aria-label={t("a11y.tripResults")}>
      <div className="atlas-pane-heading atlas-results-heading">
        <div>
          <p className="atlas-eyebrow">{t("results.yourTrip")}</p>
          <h2>{t("results.title")}</h2>
        </div>
        <span>{t("results.subtitle")}</span>
      </div>

      {!hasResults ? (
        <div className="atlas-results-empty">
          <div className="atlas-empty-route" aria-hidden="true">
            <span />
            <Route />
            <span />
          </div>
          <h3>{t("results.emptyTitle")}</h3>
          <p>{t("results.emptyBody")}</p>
          <small>{t("results.progressNote")}</small>
        </div>
      ) : (
        <div className="atlas-results-scroll">
          {handbook && (
            <div className="atlas-trip-hero">
              <div className="atlas-trip-hero-route" aria-hidden="true" />
              <p className="atlas-eyebrow">{t("results.route")}</p>
              <h3>{handbook.trip_title || t("results.yourTrip")}</h3>
              <div className="atlas-trip-meta">
                {handbook.route_cities.length > 0 && (
                  <span><Route />{handbook.route_cities.join(" → ")}</span>
                )}
                {handbook.start_date && handbook.end_date && (
                  <span>
                    <CalendarDays />
                    {dateFormatter.format(new Date(handbook.start_date))} – {dateFormatter.format(new Date(handbook.end_date))}
                  </span>
                )}
                {handbook.traveller_names.length > 0 && (
                  <span>
                    <Users />
                    {t("results.travellerCount", { count: handbook.traveller_names.length })}
                  </span>
                )}
              </div>
            </div>
          )}

          {outcomes.length > 0 && (
            <section className="atlas-outcomes" aria-labelledby="component-status-title">
              <div className="atlas-section-title-row">
                <h3 id="component-status-title">{t("results.componentStatus")}</h3>
                <p>{t("results.progressNote")}</p>
              </div>
              <div className="atlas-outcome-grid">
                {outcomes.map(([key, outcome]) => (
                  <article key={key} className={cn("atlas-outcome-card", statusTone(outcome.status))}>
                    <div>
                      <strong>
                        {COMPONENT_LABELS[key]
                          ? agentsT(COMPONENT_LABELS[key])
                          : resultsT("overview")}
                      </strong>
                      <span>{resultsT(STATUS_LABELS[outcome.status])}</span>
                    </div>
                    <small>{t("results.evidenceItems", { count: outcome.evidence_count ?? 0 })}</small>
                    {outcome.missing_fields && outcome.missing_fields.length > 0 && (
                      <small>{t("results.missingFields", { fields: outcome.missing_fields.join(", ") })}</small>
                    )}
                    {outcome.message && <p>{outcome.message}</p>}
                  </article>
                ))}
              </div>
            </section>
          )}

          {readiness?.limitations && readiness.limitations.length > 0 && (
            <section className="atlas-limitations">
              <h3><AlertCircle />{t("results.limitations")}</h3>
              <ul>
                {readiness.limitations.map((limitation) => (
                  <li key={limitation}>{limitation}</li>
                ))}
              </ul>
            </section>
          )}

          <div className="atlas-existing-results">
            <ResultsPanel />
          </div>

          {consultationUrl && (
            <aside className="atlas-consultation">
              <p className="atlas-eyebrow">{t("consultation.eyebrow")}</p>
              <h3>{t("consultation.title")}</h3>
              <p>{t("consultation.body")}</p>
              <a href={consultationUrl} target="_blank" rel="noopener noreferrer">
                {t("consultation.cta")} <ExternalLink className="h-4 w-4" />
              </a>
            </aside>
          )}
        </div>
      )}
    </section>
  );
}
