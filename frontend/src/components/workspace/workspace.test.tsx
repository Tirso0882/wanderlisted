import { NextIntlClientProvider } from "next-intl";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import en from "../../../messages/en.json";
import pl from "../../../messages/pl.json";
import { MessageBubble } from "@/components/chat/message-bubble";
import { DestinationTab } from "@/components/results/destination-tab";
import { INITIAL_AGENTS, useChatStore } from "@/stores/chat-store";
import { LocaleSwitcher } from "./locale-switcher";
import { ServiceScopeCard } from "./service-scope-card";
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

  it("renders and submits a typed Polish service-scope offer", async () => {
    const sendMessage = vi.fn();
    useChatStore.setState({
      sendMessage,
      components: {
        service_scope_offer: {
          selected_capabilities: ["flights", "hotels"],
          offered_capabilities: ["restaurants", "activities", "budget"],
          request_fingerprint: "scope-fingerprint",
        },
      },
    });

    renderIntl(<ServiceScopeCard />, "pl");
    const user = userEvent.setup();

    expect(screen.getByRole("heading", { name: /Dodać więcej usług/i })).toBeVisible();
    expect(screen.getByRole("checkbox", { name: "Restauracje" })).toBeVisible();
    expect(screen.getByRole("checkbox", { name: "Atrakcje" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Dodaj wszystkie" })).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Tylko obecne usługi" }),
    ).toBeVisible();
    await user.click(screen.getByRole("checkbox", { name: "Atrakcje" }));
    await user.click(screen.getByRole("button", { name: "Dodaj wybrane" }));
    expect(sendMessage).toHaveBeenCalledWith(
      "Uwzględnij wybrane usługi.",
      "pl",
      {
        action: "include_selected",
        selected_capabilities: ["activities"],
        request_fingerprint: "scope-fingerprint",
      },
    );
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

  it("renders a high-risk advisory as a passive warning", () => {
    renderIntl(
      <DestinationTab
        safety={null}
        safetyWarning={{
          advisory_level: "red",
          summary: "Do not travel.",
          message: "Official guidance reports a high travel risk.",
          non_blocking: true,
        }}
        culture={null}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Official guidance reports a high travel risk.",
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
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
