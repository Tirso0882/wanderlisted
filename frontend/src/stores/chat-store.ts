import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { streamChat, type StreamCallbacks } from "@/lib/api/stream";
import type {
  AgentName,
  AgentStatus,
  InterruptData,
  BudgetBreakdown,
  TripHandbook,
} from "@/lib/types";

// ── Message types ───────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

// ── Agent tracking ──────────────────────────────────────────────────────

export interface AgentState {
  name: AgentName;
  status: AgentStatus;
}

// ── View modes ──────────────────────────────────────────────────────────

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

// ── Store shape ─────────────────────────────────────────────────────────

interface ChatState {
  // Conversation
  messages: ChatMessage[];
  sessionId: string | null;
  runId: string | null;

  // Streaming
  isStreaming: boolean;
  streamingContent: string;
  abortController: AbortController | null;

  // Agent tracking
  agents: Record<AgentName, AgentStatus>;

  // HITL
  interruptData: InterruptData | null;

  // Structured results
  budget: BudgetBreakdown | null;
  components: Record<string, unknown> | null;
  handbook: TripHandbook | null;
  isMockMode: boolean;

  // View state
  activeView: ViewMode;

  // Actions
  sendMessage: (content: string) => void;
  stopStreaming: () => void;
  clearChat: () => void;
  goHome: () => void;
  setActiveView: (view: ViewMode) => void;
  setInterruptData: (data: InterruptData | null) => void;
  setComponents: (components: Record<string, unknown> | null) => void;
  setBudget: (budget: BudgetBreakdown | null) => void;
  setHandbook: (handbook: TripHandbook | null) => void;
}

// ── Helpers ─────────────────────────────────────────────────────────────

let _nextId = 0;
function msgId(): string {
  return `msg_${Date.now()}_${++_nextId}`;
}

const INITIAL_AGENTS: Record<AgentName, AgentStatus> = {
  FlightsAgent: "idle",
  HotelsAgent: "idle",
  DestinationAgent: "idle",
  RestaurantsAgent: "idle",
  ActivitiesAgent: "idle",
  TransportationAgent: "idle",
  BudgetAgent: "idle",
  ItineraryAgent: "idle",
};

/** Detect intent from user message to route the view */
function detectIntent(message: string): ViewMode | null {
  const lower = message.toLowerCase();
  const patterns: [ViewMode, RegExp][] = [
    ["flights", /\b(flight|fly|airport|airline|book.*fly|plane)\b/],
    ["hotels", /\b(hotel|stay|accommodation|lodging|hostel|airbnb|check.?in)\b/],
    ["destination", /\b(destination|city|country|where.*(go|visit)|guide|info.*(about|on))\b/],
    ["activities", /\b(activit|thing.*to.*do|attraction|sightseeing|museum|tour|adventure)\b/],
    ["restaurants", /\b(restaurant|food|eat|dining|cuisine|meal|lunch|dinner|breakfast|cafe)\b/],
    ["transport", /\b(transport|getting.*around|taxi|uber|subway|metro|bus|train|rental.*car)\b/],
    ["budget", /\b(budget|cost|price|expense|money|spend|cheap|afford)\b/],
    ["itinerary", /\b(itinerary|schedule|plan.*trip|day.*plan|full.*plan)\b/],
    ["full-plan", /\b(full.*trip|complete.*plan|plan.*everything|whole.*trip)\b/],
  ];

  for (const [view, regex] of patterns) {
    if (regex.test(lower)) return view;
  }
  return null;
}

// ── Store ───────────────────────────────────────────────────────────────

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
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
      activeView: "home" as ViewMode,

      sendMessage: (content: string) => {
        const state = get();
        if (state.isStreaming) return;

        // Detect which view to show based on user intent
        const detectedView = detectIntent(content);

        // Add user message
        const userMsg: ChatMessage = {
          id: msgId(),
          role: "user",
          content,
          timestamp: Date.now(),
        };

        set({
          messages: [...state.messages, userMsg],
          isStreaming: true,
          streamingContent: "",
          interruptData: null,
          ...(detectedView ? { activeView: detectedView } : {}),
        });

        // Start streaming
        const callbacks: StreamCallbacks = {
          onSession: (sessionId) => {
            set({ sessionId });
          },
          onToken: (token) => {
            set((s) => ({
              streamingContent: s.streamingContent + token,
            }));
          },
          onAgentStart: (agentName) => {
            const name = agentName as AgentName;
            // Auto-route to the correct view when agent starts
            const agentViewMap: Record<AgentName, ViewMode> = {
              FlightsAgent: "flights",
              HotelsAgent: "hotels",
              DestinationAgent: "destination",
              RestaurantsAgent: "restaurants",
              ActivitiesAgent: "activities",
              TransportationAgent: "transport",
              BudgetAgent: "budget",
              ItineraryAgent: "itinerary",
            };
            const targetView = agentViewMap[name];
            set((s) => ({
              agents: { ...s.agents, [name]: "running" as AgentStatus },
              ...(targetView && s.activeView === "home" ? { activeView: targetView } : {}),
            }));
          },
          onToolResult: (_toolName) => {
            set((s) => {
              const updated = { ...s.agents };
              for (const [key, status] of Object.entries(updated)) {
                if (status === "running") {
                  updated[key as AgentName] = "completed";
                }
              }
              return { agents: updated };
            });
          },
          onInterrupt: (gate, data) => {
            const current = get();
            const finalContent = current.streamingContent;

            if (finalContent.trim()) {
              const assistantMsg: ChatMessage = {
                id: msgId(),
                role: "assistant",
                content: finalContent,
                timestamp: Date.now(),
              };
              set((s) => ({
                messages: [...s.messages, assistantMsg],
              }));
            }

            set({
              isStreaming: false,
              streamingContent: "",
              abortController: null,
              interruptData: { gate, ...(typeof data === "object" && data ? data : {}) } as InterruptData,
            });
          },
          onError: (error) => {
            const assistantMsg: ChatMessage = {
              id: msgId(),
              role: "assistant",
              content: `Error: ${error}`,
              timestamp: Date.now(),
            };
            set((s) => ({
              messages: [...s.messages, assistantMsg],
              isStreaming: false,
              streamingContent: "",
              abortController: null,
            }));
          },
          onDone: (data: Record<string, unknown>) => {
            const current = get();
            const finalContent = current.streamingContent;

            if (finalContent.trim()) {
              const assistantMsg: ChatMessage = {
                id: msgId(),
                role: "assistant",
                content: finalContent,
                timestamp: Date.now(),
              };
              set((s) => ({
                messages: [...s.messages, assistantMsg],
              }));
            }

            const interrupted = data?.interrupted as boolean | undefined;
            const interruptPayload = data?.interrupt_data as InterruptData | undefined;

            set({
              isStreaming: false,
              streamingContent: "",
              abortController: null,
              runId: (data?.run_id as string) ?? current.runId,
              interruptData: interrupted ? (interruptPayload ?? null) : null,
              budget: (data?.budget as BudgetBreakdown) ?? current.budget,
              components:
                (data?.components as Record<string, unknown>) ?? current.components,
            });
          },
        };

        // Map activeView to backend agent name for single-agent isolation
        const viewToAgent: Partial<Record<ViewMode, string>> = {
          flights: "FlightsAgent",
          hotels: "HotelsAgent",
          destination: "DestinationAgent",
          restaurants: "RestaurantsAgent",
          activities: "ActivitiesAgent",
          transport: "TransportationAgent",
          budget: "BudgetAgent",
          itinerary: "ItineraryAgent",
        };

        const currentView = detectedView ?? state.activeView;
        const targetAgent = viewToAgent[currentView];

        const controller = streamChat(
          {
            message: content,
            session_id: state.sessionId ?? undefined,
            ...(targetAgent ? { target_agent: targetAgent } : {}),
          },
          callbacks,
        );

        set({ abortController: controller });
      },

      stopStreaming: () => {
        const { abortController, streamingContent, messages } = get();
        abortController?.abort();

        if (streamingContent.trim()) {
          const assistantMsg: ChatMessage = {
            id: msgId(),
            role: "assistant",
            content: streamingContent + " [stopped]",
            timestamp: Date.now(),
          };
          set({
            messages: [...messages, assistantMsg],
            isStreaming: false,
            streamingContent: "",
            abortController: null,
          });
        } else {
          set({
            isStreaming: false,
            streamingContent: "",
            abortController: null,
          });
        }
      },

      clearChat: () => {
        const { abortController } = get();
        abortController?.abort();
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
        });
      },

      goHome: () => {
        set({ activeView: "home" });
      },

      setActiveView: (view) => set({ activeView: view }),
      setInterruptData: (data) => set({ interruptData: data }),
      setComponents: (components) => set({ components }),
      setBudget: (budget) => set({ budget }),
      setHandbook: (handbook) => set({ handbook }),
    }),
    {
      name: "wanderlisted-chat",
      storage: createJSONStorage(() =>
        typeof window !== "undefined"
          ? sessionStorage
          : {
              getItem: () => null,
              setItem: () => {},
              removeItem: () => {},
            },
      ),
      version: 3,
      migrate: () => ({ messages: [], sessionId: null }),
      partialize: (state) => ({
        messages: state.messages,
        sessionId: state.sessionId,
      }),
    },
  ),
);
