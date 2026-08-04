"use client";

import { useTranslations } from "next-intl";
import type { AgentName, AgentStatus } from "@/lib/types";
import { useChatStore } from "@/stores/chat-store";

export function TruthfulLoading() {
  const t = useTranslations("loading");
  const agentsT = useTranslations("agents");
  const agents = useChatStore((state) => state.agents);
  const activeAgents = (Object.entries(agents) as [AgentName, AgentStatus][]).filter(
    ([, status]) => status === "running",
  );

  return (
    <div className="atlas-loading" role="status" aria-live="polite">
      <div className="atlas-loading-route" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div>
        <p className="font-semibold text-[var(--atlas-navy)]">
          {activeAgents.length > 0
            ? activeAgents.map(([name]) => agentsT(name)).join(" · ")
            : t("thinking")}
        </p>
        <p className="mt-0.5 text-xs text-[var(--atlas-ink-soft)]">
          {t("body")}
        </p>
      </div>
    </div>
  );
}
