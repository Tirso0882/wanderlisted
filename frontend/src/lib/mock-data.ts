import type { TripHandbook, BudgetBreakdown } from "@/lib/types";

/**
 * Load the mock handbook data from the public folder.
 * Used for UI development without LLM API access.
 */
export async function loadMockHandbook(): Promise<TripHandbook> {
  const res = await fetch("/mock-handbook.json");
  if (!res.ok) throw new Error("Failed to load mock handbook data");
  return res.json() as Promise<TripHandbook>;
}

/**
 * Extract a BudgetBreakdown from the flat handbook fields.
 */
export function extractBudget(handbook: TripHandbook): BudgetBreakdown {
  return {
    flights: handbook.budget_flights,
    accommodation: handbook.budget_accommodation,
    transport: handbook.budget_transport,
    meals: handbook.budget_meals,
    activities: handbook.budget_activities,
    misc: handbook.budget_misc,
    total: handbook.budget_total,
    per_person: handbook.budget_per_person,
    currency: handbook.budget_base_currency ?? "USD",
    summary: handbook.budget_summary,
    base_currency: handbook.budget_base_currency ?? "USD",
    display_currency:
      handbook.budget_display_currency ?? handbook.budget_base_currency ?? "USD",
    display_breakdown: handbook.budget_display_breakdown ?? null,
    coverage_status: handbook.budget_coverage_status ?? "partial",
    missing_categories: handbook.budget_missing_categories ?? [],
    estimated_categories: handbook.budget_estimated_categories ?? [],
    assumptions: handbook.budget_assumptions ?? [],
    reserve_recommendation: handbook.budget_reserve_recommendation ?? 0,
    display_reserve_recommendation:
      handbook.budget_display_reserve_recommendation ?? null,
    contingency_included: handbook.budget_contingency_included ?? false,
  };
}
