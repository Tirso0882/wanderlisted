// API request/response types matching src/api/main.py

import type {
  BudgetBreakdown,
  ItineraryPlan,
  TravelReadinessReport,
  TripHandbook,
} from "./itinerary";
import type { AppLocale } from "@/i18n/config";

export type ComponentOutcomeStatus =
  | "queued"
  | "running"
  | "completed"
  | "partial"
  | "needs_user_input"
  | "no_inventory"
  | "blocked_external"
  | "failed"
  | "stale";

export interface ComponentOutcome {
  component: string;
  status: ComponentOutcomeStatus;
  missing_fields?: string[];
  message?: string;
  error_category?: string;
  error_detail?: string;
  tools_called?: string[];
  evidence_count?: number;
  request_fingerprint?: string;
}

export interface SafetyWarning {
  advisory_level: "orange" | "red";
  summary: string;
  message: string;
  non_blocking: true;
}

export type RequestedCapability =
  | "flights"
  | "hotels"
  | "travel_readiness"
  | "restaurants"
  | "activities"
  | "transportation"
  | "budget"
  | "itinerary";

export interface ServiceScopeOffer {
  selected_capabilities: RequestedCapability[];
  offered_capabilities: RequestedCapability[];
  request_fingerprint: string;
}

export type ServiceScopeDecision =
  | {
      action: "include_all" | "selected_only";
      request_fingerprint: string;
    }
  | {
      action: "include_selected";
      selected_capabilities: RequestedCapability[];
      request_fingerprint: string;
    };

export interface StructuredComponents extends Record<string, unknown> {
  itinerary_structured?: ItineraryPlan | null;
  handbook_structured?: TripHandbook | null;
  budget_structured?: BudgetBreakdown | null;
  readiness?: { data?: TravelReadinessReport | null };
  readiness_preflight?: { data?: TravelReadinessReport | null };
  safety_warning?: SafetyWarning;
  service_scope_offer?: ServiceScopeOffer;
  component_results?: Record<string, ComponentOutcome>;
}

// ── Chat ────────────────────────────────────────────────────────────────

export interface ChatRequest {
  message: string;
  session_id?: string;
  service_scope_decision?: ServiceScopeDecision;
  ui_locale?: AppLocale;
}

export interface ChatResponse {
  message: string;
  session_id: string;
  run_id: string | null;
  interrupted: boolean;
  interrupt_data: InterruptData | null;
  budget: BudgetBreakdown | null;
  components: StructuredComponents | null;
  locale: string;
}

// ── HITL ────────────────────────────────────────────────────────────────

export interface InterruptData {
  gate: "budget_review" | "human_review";
  summary: string;
  [key: string]: unknown;
}

export interface ResumeRequest {
  session_id: string;
  decision: ResumeDecision;
  ui_locale?: AppLocale;
}

export type ResumeDecision =
  | {
      gate: "human_review";
      action: "approved" | "edited" | "rejected";
      feedback?: string;
    }
  | { gate: "budget_review"; action: "proceed" | "cancel" }
  | {
      gate: "budget_review";
      action: "adjust_target";
      new_budget: number;
    }
  | { approved: boolean; feedback?: string };

export interface ResumeResponse {
  message: string;
  session_id: string;
  status: "resumed" | "completed" | "interrupted";
  interrupted: boolean;
  interrupt_data: InterruptData | null;
  budget: BudgetBreakdown | null;
  components: StructuredComponents | null;
  locale: string;
}

// ── Session ─────────────────────────────────────────────────────────────

export interface SessionInfo {
  session_id: string;
  message_count: number;
}

export interface SessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  locale: AppLocale;
  message_count: number;
}

export interface SessionListResponse {
  items: SessionSummary[];
  next_cursor: string | null;
}

export interface SessionSnapshot {
  session: SessionSummary | null;
  messages: HistoryMessage[];
  interrupted: boolean;
  interrupt_data: InterruptData | null;
  budget: BudgetBreakdown | null;
  components: StructuredComponents | null;
  locale: string;
}

export interface AccountPreferencesResponse {
  locale: AppLocale | null;
}

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

// ── Feedback ────────────────────────────────────────────────────────────

export interface FeedbackRequest {
  run_id: string;
  score: number;
  comment?: string;
  key?: string;
}

// ── SSE Event Types ─────────────────────────────────────────────────────

export type SSEEventType =
  | "session"
  | "token"
  | "agent_start"
  | "tool_call"
  | "tool_result"
  | "interrupt"
  | "error"
  | "done";

export interface SSEEvent {
  event: SSEEventType;
  data: string;
}

// ── Agent names (for activity bar) ──────────────────────────────────────

export const AGENT_NAMES = [
  "FlightsAgent",
  "HotelsAgent",
  "TravelReadinessAgent",
  "RestaurantsAgent",
  "ActivitiesAgent",
  "TransportationAgent",
  "BudgetAgent",
  "ItineraryAgent",
] as const;

export type AgentName = (typeof AGENT_NAMES)[number];

export type AgentStatus = "idle" | "running" | "completed" | "error";
