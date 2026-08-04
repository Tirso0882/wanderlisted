import { NextIntlClientProvider } from "next-intl";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import pl from "../../../messages/pl.json";
import { MessageBubble } from "@/components/chat/message-bubble";
import { INITIAL_AGENTS, useChatStore } from "@/stores/chat-store";
import { InlineHitlCard } from "./inline-hitl-card";
import { LocaleSwitcher } from "./locale-switcher";
import { SuggestionChips } from "./suggestion-chips";
import { TruthfulLoading } from "./truthful-loading";

const { refreshMock } = vi.hoisted(() => ({ refreshMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: refreshMock }),
}));

function renderIntl(node: React.ReactNode, locale: "en" | "pl" = "en") {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={locale === "pl" ? pl : en}
      timeZone="Europe/Warsaw"
    >
      {node}
    </NextIntlClientProvider>,
  );
}

beforeEach(() => {
  refreshMock.mockReset();
  useChatStore.setState({
    messages: [],
    sessionId: null,
    isStreaming: false,
    streamingContent: "",
    abortController: null,
    agents: { ...INITIAL_AGENTS },
    interruptData: null,
    components: null,
    budget: null,
    handbook: null,
    errorKey: null,
  });
});

describe("Atlas chat primitives", () => {
  it("renders exactly three contextual suggestion chips", () => {
    renderIntl(<SuggestionChips />);
    const region = screen.getByLabelText("Suggested follow-ups");
    expect(within(region).getAllByRole("button")).toHaveLength(3);
  });

  it("right-aligns user messages by role", () => {
    const { container } = renderIntl(
      <MessageBubble
        message={{ id: "one", role: "user", content: "Warsaw", timestamp: 0 }}
      />,
    );
    expect(container.querySelector('[data-message-role="user"]')).toHaveClass(
      "atlas-message-row-user",
    );
  });

  it("announces only graph-reported active work without a percentage", () => {
    useChatStore.setState({
      isStreaming: true,
      agents: { ...INITIAL_AGENTS, FlightsAgent: "running" },
    });
    renderIntl(<TruthfulLoading />);
    expect(screen.getByRole("status")).toHaveTextContent("Flights");
    expect(screen.getByRole("status")).not.toHaveTextContent("%");
  });

  it("preserves partial output when the user stops generation", () => {
    const controller = new AbortController();
    useChatStore.setState({
      messages: [],
      isStreaming: true,
      streamingContent: "Verified so far",
      abortController: controller,
    });
    act(() => useChatStore.getState().stopStreaming());
    expect(controller.signal.aborted).toBe(true);
    expect(useChatStore.getState().messages.at(-1)).toMatchObject({
      content: "Verified so far",
      stopped: true,
    });
  });

  it("restores an inline HITL card with Polish controls", () => {
    useChatStore.setState({
      sessionId: "session-1",
      interruptData: {
        gate: "safety_review",
        summary: "Sprawdź oficjalne ostrzeżenie.",
        advisory_level: "orange",
      },
    });
    renderIntl(<InlineHitlCard />, "pl");
    expect(screen.getByText("Potrzebuję Twojej decyzji")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Rozumiem, kontynuuj/i })).toBeVisible();
  });

  it("persists a guest language selection in the locale cookie", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderIntl(<LocaleSwitcher />);
    await user.click(screen.getByRole("button", { name: "Przełącz interfejs na polski" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/locale",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ locale: "pl" }),
      }),
    );
    expect(refreshMock).toHaveBeenCalledOnce();
    vi.unstubAllGlobals();
  });
});
