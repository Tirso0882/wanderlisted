import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { AppLocale } from "@/i18n/config";
import { rememberBrowserSession } from "@/lib/api/sessions";
import { streamChat, type StreamCallbacks } from "@/lib/api/stream";
import type {
  AgentName,
  AgentStatus,
  BudgetBreakdown,
  InterruptData,
  ResumeResponse,
  ServiceScopeDecision,
  SessionSnapshot,
  StructuredComponents,
  TripHandbook,
} from "@/lib/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  stopped?: boolean;
}

export type ViewMode =
  | "home"
  | "flights"
  | "hotels"
  | "destination"
  | "activities"
  | "restaurants"
  | "transport"
  | "budget"
  | "itinerary"
  | "full-plan";

export type ChatErrorKey = "stream" | "network" | "preferences" | "save" | null;

interface ChatState {
  messages: ChatMessage[];
  sessionId: string | null;
  runId: string | null;
  responseLocale: string;
  isStreaming: boolean;
  streamingContent: string;
  abortController: AbortController | null;
  agents: Record<AgentName, AgentStatus>;
  interruptData: InterruptData | null;
  budget: BudgetBreakdown | null;
  components: StructuredComponents | null;
  handbook: TripHandbook | null;
  isMockMode: boolean;
  activeView: ViewMode;
  errorKey: ChatErrorKey;
  sendMessage: (
    content: string,
    uiLocale?: AppLocale,
    serviceScopeDecision?: ServiceScopeDecision,
  ) => void;
  stopStreaming: () => void;
  clearChat: () => void;
  goHome: () => void;
  setActiveView: (view: ViewMode) => void;
  setInterruptData: (data: InterruptData | null) => void;
  setComponents: (components: StructuredComponents | null) => void;
  setBudget: (budget: BudgetBreakdown | null) => void;
  setHandbook: (handbook: TripHandbook | null) => void;
  setErrorKey: (error: ChatErrorKey) => void;
  restoreSnapshot: (sessionId: string, snapshot: SessionSnapshot) => void;
  applyResumeResponse: (response: ResumeResponse) => void;
}

let nextId = 0;
function messageId(): string {
  nextId += 1;
  return `msg_${Date.now()}_${nextId}`;
}

export const INITIAL_AGENTS: Record<AgentName, AgentStatus> = {
  FlightsAgent: "idle",
  HotelsAgent: "idle",
  TravelReadinessAgent: "idle",
  RestaurantsAgent: "idle",
  ActivitiesAgent: "idle",
  TransportationAgent: "idle",
  BudgetAgent: "idle",
  ItineraryAgent: "idle",
};

function isAgentName(value: string): value is AgentName {
  return Object.prototype.hasOwnProperty.call(INITIAL_AGENTS, value);
}

function extractHandbook(
  components: StructuredComponents | null,
): TripHandbook | null | undefined {
  if (!components || !("handbook_structured" in components)) return undefined;
  const candidate = components.handbook_structured;
  return candidate && typeof candidate === "object" && Array.isArray(candidate.days)
    ? candidate
    : null;
}

function detectIntent(message: string): ViewMode | null {
  const lower = message.toLowerCase();
  const patterns: [ViewMode, RegExp][] = [
    ["flights", /\b(flight|flights|lot|loty|samolot)\b/],
    ["hotels", /\b(hotel|hotels|nocleg|noclegi)\b/],
    ["destination", /\b(safety|visa|weather|bezpieczeń|wiza|pogoda)\b/],
    ["activities", /\b(activities|attractions|atrakcje|zwiedzanie)\b/],
    ["restaurants", /\b(restaurant|food|restaurants|jedzenie|restauracje)\b/],
    ["transport", /\b(transport|route|routes|trasa|trasy)\b/],
    ["budget", /\b(budget|cost|price|budżet|koszt|cena)\b/],
    ["itinerary", /\b(itinerary|schedule|plan|harmonogram)\b/],
  ];
  return patterns.find(([, pattern]) => pattern.test(lower))?.[0] ?? null;
}

function agentsFromComponents(
  components: StructuredComponents | null,
): Record<AgentName, AgentStatus> {
  const next = { ...INITIAL_AGENTS };
  const mapping: Record<string, AgentName> = {
    flights: "FlightsAgent",
    hotels: "HotelsAgent",
    readiness: "TravelReadinessAgent",
    readiness_preflight: "TravelReadinessAgent",
    restaurants: "RestaurantsAgent",
    activities: "ActivitiesAgent",
    transportation: "TransportationAgent",
    budget: "BudgetAgent",
    itinerary: "ItineraryAgent",
  };
  for (const [component, outcome] of Object.entries(
    components?.component_results ?? {},
  )) {
    const name = mapping[component];
    if (!name) continue;
    next[name] = ["completed", "partial", "no_inventory"].includes(outcome.status)
      ? "completed"
      : ["failed", "blocked_external", "stale"].includes(outcome.status)
        ? "error"
        : outcome.status === "running"
          ? "running"
          : "idle";
  }
  return next;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      messages: [],
      sessionId: null,
      runId: null,
      responseLocale: "en",
      isStreaming: false,
      streamingContent: "",
      abortController: null,
      agents: { ...INITIAL_AGENTS },
      interruptData: null,
      budget: null,
      components: null,
      handbook: null,
      isMockMode: false,
      activeView: "home",
      errorKey: null,

      sendMessage: (content, uiLocale = "en", serviceScopeDecision) => {
        const state = get();
        const trimmed = content.trim();
        if (!trimmed || state.isStreaming) return;
        const detectedView = detectIntent(trimmed);
        const activeView =
          detectedView ?? (state.activeView === "home" ? "full-plan" : state.activeView);
        const userMessage: ChatMessage = {
          id: messageId(),
          role: "user",
          content: trimmed,
          timestamp: Date.now(),
        };

        set({
          messages: [...state.messages, userMessage],
          isStreaming: true,
          streamingContent: "",
          interruptData: null,
          activeView,
          errorKey: null,
        });

        const callbacks: StreamCallbacks = {
          onSession: (sessionId) => {
            rememberBrowserSession(sessionId);
            set({ sessionId });
          },
          onToken: (token) =>
            set((current) => ({ streamingContent: current.streamingContent + token })),
          onAgentStart: (agentName) => {
            if (!isAgentName(agentName)) return;
            set((current) => ({
              agents: { ...current.agents, [agentName]: "running" },
            }));
          },
          onToolResult: () =>
            set((current) => {
              const agents = { ...current.agents };
              for (const name of Object.keys(agents) as AgentName[]) {
                if (agents[name] === "running") agents[name] = "completed";
              }
              return { agents };
            }),
          onInterrupt: (_gate, data) => {
            const current = get();
            const assistantMessage: ChatMessage[] = current.streamingContent.trim()
              ? [
                  {
                    id: messageId(),
                    role: "assistant",
                    content: current.streamingContent,
                    timestamp: Date.now(),
                  },
                ]
              : [];
            set({
              messages: [...current.messages, ...assistantMessage],
              isStreaming: false,
              streamingContent: "",
              abortController: null,
              interruptData: (typeof data === "object" && data
                ? data
                : null) as InterruptData | null,
            });
          },
          onError: () =>
            set({
              isStreaming: false,
              streamingContent: "",
              abortController: null,
              errorKey: "stream",
            }),
          onDone: (data) => {
            const current = get();
            const assistantMessage: ChatMessage[] = current.streamingContent.trim()
              ? [
                  {
                    id: messageId(),
                    role: "assistant",
                    content: current.streamingContent,
                    timestamp: Date.now(),
                  },
                ]
              : [];
            const incomingComponents = data.components as
              | StructuredComponents
              | null
              | undefined;
            const components =
              incomingComponents === undefined ? current.components : incomingComponents;
            const handbook = extractHandbook(components);
            const interrupted = data.interrupted as boolean | undefined;
            set({
              messages: [...current.messages, ...assistantMessage],
              isStreaming: false,
              streamingContent: "",
              abortController: null,
              runId: (data.run_id as string | null | undefined) ?? current.runId,
              responseLocale:
                typeof data.locale === "string" && /^[a-z]{2,3}$/.test(data.locale)
                  ? data.locale
                  : current.responseLocale,
              interruptData:
                interrupted === undefined
                  ? current.interruptData
                  : interrupted
                    ? ((data.interrupt_data as InterruptData | null) ??
                      current.interruptData)
                    : null,
              budget:
                (data.budget as BudgetBreakdown | null | undefined) ?? current.budget,
              components,
              ...(handbook !== undefined ? { handbook } : {}),
              agents: components
                ? agentsFromComponents(components)
                : (Object.fromEntries(
                    Object.entries(current.agents).map(([name, status]) => [
                      name,
                      status === "running" ? "completed" : status,
                    ]),
                  ) as Record<AgentName, AgentStatus>),
            });
          },
        };

        const controller = streamChat(
          {
            message: trimmed,
            session_id: state.sessionId ?? undefined,
            service_scope_decision: serviceScopeDecision,
            ui_locale: uiLocale,
          },
          callbacks,
        );
        set({ abortController: controller, responseLocale: uiLocale });
      },

      stopStreaming: () => {
        const current = get();
        current.abortController?.abort();
        const stoppedMessage: ChatMessage = {
          id: messageId(),
          role: "assistant",
          content: current.streamingContent,
          timestamp: Date.now(),
          stopped: true,
        };
        set({
          messages: [...current.messages, stoppedMessage],
          isStreaming: false,
          streamingContent: "",
          abortController: null,
          agents: Object.fromEntries(
            Object.entries(current.agents).map(([name, status]) => [
              name,
              status === "running" ? "idle" : status,
            ]),
          ) as Record<AgentName, AgentStatus>,
        });
      },

      clearChat: () => {
        get().abortController?.abort();
        set({
          messages: [],
          sessionId: null,
          runId: null,
          isStreaming: false,
          streamingContent: "",
          abortController: null,
          agents: { ...INITIAL_AGENTS },
          interruptData: null,
          budget: null,
          components: null,
          handbook: null,
          isMockMode: false,
          activeView: "home",
          errorKey: null,
        });
      },

      goHome: () => set({ activeView: "home" }),
      setActiveView: (activeView) => set({ activeView }),
      setInterruptData: (interruptData) => set({ interruptData }),
      setComponents: (components) => {
        const handbook = extractHandbook(components);
        set({ components, ...(handbook !== undefined ? { handbook } : {}) });
      },
      setBudget: (budget) => set({ budget }),
      setHandbook: (handbook) => set({ handbook }),
      setErrorKey: (errorKey) => set({ errorKey }),
      restoreSnapshot: (sessionId, snapshot) => {
        rememberBrowserSession(sessionId);
        const components = snapshot.components;
        const handbook = extractHandbook(components);
        set({
          messages: snapshot.messages.map((message) => ({
            ...message,
            id: messageId(),
            timestamp: Date.now(),
          })),
          sessionId,
          runId: null,
          responseLocale: snapshot.locale,
          isStreaming: false,
          streamingContent: "",
          abortController: null,
          agents: agentsFromComponents(components),
          interruptData: snapshot.interrupted ? snapshot.interrupt_data : null,
          budget: snapshot.budget,
          components,
          handbook: handbook ?? null,
          activeView: "full-plan",
          errorKey: null,
        });
      },
      applyResumeResponse: (response) => {
        const current = get();
        const components = response.components;
        const handbook = extractHandbook(components);
        const assistantMessage: ChatMessage[] = response.message.trim()
          ? [
              {
                id: messageId(),
                role: "assistant",
                content: response.message,
                timestamp: Date.now(),
              },
            ]
          : [];
        set({
          messages: [...current.messages, ...assistantMessage],
          responseLocale: response.locale,
          components,
          budget: response.budget,
          ...(handbook !== undefined ? { handbook } : {}),
          agents: agentsFromComponents(components),
          interruptData: response.interrupted ? response.interrupt_data : null,
          errorKey: null,
        });
      },
    }),
    {
      name: "wanderlisted-chat",
      storage: createJSONStorage(() =>
        typeof window !== "undefined"
          ? sessionStorage
          : {
              getItem: () => null,
              setItem: () => undefined,
              removeItem: () => undefined,
            },
      ),
      version: 4,
      migrate: () => ({ messages: [], sessionId: null }),
      partialize: (state) => ({
        messages: state.messages,
        sessionId: state.sessionId,
        responseLocale: state.responseLocale,
      }),
    },
  ),
);
