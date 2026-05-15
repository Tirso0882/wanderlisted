import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { streamChat, type StreamCallbacks } from "@/lib/api/stream";
import { loadMockHandbook, extractBudget } from "@/lib/mock-data";
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
  activeTab: string;

  // Actions
  sendMessage: (content: string) => void;
  stopStreaming: () => void;
  clearChat: () => void;
  setInterruptData: (data: InterruptData | null) => void;
  setComponents: (components: Record<string, unknown> | null) => void;
  setBudget: (budget: BudgetBreakdown | null) => void;
  setHandbook: (handbook: TripHandbook | null) => void;
  setActiveTab: (tab: string) => void;
  loadMockData: () => Promise<void>;
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
      activeTab: "overview",

      sendMessage: (content: string) => {
        const state = get();
        if (state.isStreaming) return;

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
            set((s) => ({
              agents: { ...s.agents, [name]: "running" as AgentStatus },
            }));
          },
          onToolResult: (_toolName) => {
            // Mark the currently running agent as completed when its tool finishes
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

            // Check for interrupt data in the done payload
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

        const controller = streamChat(
          {
            message: content,
            session_id: state.sessionId ?? undefined,
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
          activeTab: "overview",
        });
      },

      setInterruptData: (data) => set({ interruptData: data }),
      setComponents: (components) => set({ components }),
      setBudget: (budget) => set({ budget }),
      setHandbook: (handbook) => set({ handbook }),
      setActiveTab: (tab) => set({ activeTab: tab }),

      loadMockData: async () => {
        try {
          const handbook = await loadMockHandbook();
          const budget = extractBudget(handbook);

          // Mark all agents as completed
          const completedAgents: Record<AgentName, AgentStatus> = {
            FlightsAgent: handbook.flights.length > 0 ? "completed" : "idle",
            HotelsAgent: handbook.hotels.length > 0 ? "completed" : "idle",
            DestinationAgent: "completed",
            RestaurantsAgent: "completed",
            ActivitiesAgent: "completed",
            TransportationAgent: "completed",
            BudgetAgent: budget.total > 0 ? "completed" : "idle",
            ItineraryAgent: handbook.days.length > 0 ? "completed" : "idle",
          };

          set({
            handbook,
            budget,
            agents: completedAgents,
            isMockMode: true,
            activeTab: "hotels",
          });
        } catch (err) {
          console.error("Failed to load mock data:", err);
        }
      },
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
      partialize: (state) => ({
        messages: state.messages,
        sessionId: state.sessionId,
        budget: state.budget,
        components: state.components,
        handbook: state.handbook,
        isMockMode: state.isMockMode,
      }),
    },
  ),
);
