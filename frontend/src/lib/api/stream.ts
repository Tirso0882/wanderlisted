import type { ChatRequest, SSEEventType } from "@/lib/types";

export interface StreamCallbacks {
  onSession?: (sessionId: string) => void;
  onToken?: (token: string) => void;
  onAgentStart?: (agentName: string) => void;
  onToolCall?: (toolName: string, args: string) => void;
  onToolResult?: (toolName: string, result: string) => void;
  onInterrupt?: (gate: string, data: unknown) => void;
  onError?: (error: string) => void;
  onDone?: (data: Record<string, unknown>) => void;
}

/**
 * Connect to the SSE streaming endpoint via POST.
 * Returns an AbortController so the caller can cancel.
 */
export function streamChat(
  request: ChatRequest,
  callbacks: StreamCallbacks,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch("/api/v1/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: controller.signal,
        credentials: "same-origin",
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        callbacks.onError?.(err.detail ?? `Stream error ${res.status}`);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError?.("No response body");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") {
            callbacks.onDone?.({});
            return;
          }

          try {
            const parsed = JSON.parse(raw);
            const event = (parsed.event ?? parsed.type) as SSEEventType;

            switch (event) {
              case "session":
                callbacks.onSession?.(parsed.session_id ?? parsed.data);
                break;
              case "token":
                callbacks.onToken?.(parsed.token ?? parsed.data ?? "");
                break;
              case "agent_start":
                callbacks.onAgentStart?.(parsed.agent ?? parsed.name ?? parsed.data ?? "");
                break;
              case "tool_call":
                callbacks.onToolCall?.(parsed.tool ?? "", parsed.args ?? "");
                break;
              case "tool_result":
                callbacks.onToolResult?.(parsed.tool ?? "", parsed.result ?? "");
                break;
              case "interrupt":
                callbacks.onInterrupt?.(parsed.gate ?? "", parsed.data ?? null);
                break;
              case "error":
                callbacks.onError?.(parsed.message ?? parsed.data ?? "Unknown error");
                break;
              case "done":
                callbacks.onDone?.(parsed);
                return;
              default:
                // Fallback: if no event type, treat as token
                if (parsed.token || parsed.data) {
                  callbacks.onToken?.(parsed.token ?? parsed.data ?? "");
                }
            }
          } catch {
            // Non-JSON line — might be a raw token
            if (raw) callbacks.onToken?.(raw);
          }
        }
      }

      callbacks.onDone?.({});
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      callbacks.onError?.(err instanceof Error ? err.message : "Stream failed");
    }
  })();

  return controller;
}
