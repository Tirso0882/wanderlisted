// API request/response types matching src/api/main.py

import type { BudgetBreakdown } from "./itinerary";

// ── Chat ────────────────────────────────────────────────────────────────

export interface ChatRequest {
  message: string;
  session_id?: string;
  target_agent?: string;
}

export interface ChatResponse {
  message: string;
  session_id: string;
  run_id: string | null;
  interrupted: boolean;
  interrupt_data: InterruptData | null;
  budget: BudgetBreakdown | null;
  components: Record<string, unknown> | null;
}

// ── HITL ────────────────────────────────────────────────────────────────

export interface InterruptData {
  gate: "safety_review" | "budget_review" | "human_review";
  summary: string;
  [key: string]: unknown;
}

export interface ResumeRequest {
  session_id: string;
  decision: ResumeDecision;
}

export type ResumeDecision =
  | { gate: "safety_review"; approved: boolean }
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
  components: Record<string, unknown> | null;
}

// ── Session ─────────────────────────────────────────────────────────────

export interface SessionInfo {
  session_id: string;
  message_count: number;
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
