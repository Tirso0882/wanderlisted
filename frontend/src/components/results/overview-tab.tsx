"use client";

import {
  Bus,
  CheckCircle2,
  Circle,
  ClipboardList,
  Compass,
  DollarSign,
  Hotel,
  Loader2,
  Plane,
  ShieldCheck,
  Utensils,
  type LucideIcon,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Card, CardContent } from "@/components/ui/card";
import { localeTag, type AppLocale } from "@/i18n/config";
import { formatCurrency } from "@/lib/format-currency";
import type { AgentName, AgentStatus } from "@/lib/types";
import { useChatStore } from "@/stores/chat-store";

const AGENT_META: { name: AgentName; icon: LucideIcon }[] = [
  { name: "FlightsAgent", icon: Plane },
  { name: "HotelsAgent", icon: Hotel },
  { name: "TravelReadinessAgent", icon: ShieldCheck },
  { name: "ActivitiesAgent", icon: Compass },
  { name: "RestaurantsAgent", icon: Utensils },
  { name: "TransportationAgent", icon: Bus },
  { name: "BudgetAgent", icon: DollarSign },
  { name: "ItineraryAgent", icon: ClipboardList },
];

const STATUS_ICON: Record<AgentStatus, LucideIcon> = {
  idle: Circle,
  running: Loader2,
  completed: CheckCircle2,
  error: Circle,
};

const STATUS_STYLE: Record<AgentStatus, string> = {
  idle: "text-muted-foreground/40",
  running: "text-primary animate-spin",
  completed: "text-emerald-600",
  error: "text-destructive",
};

export function OverviewTab() {
  const locale = useLocale() as AppLocale;
  const agentsT = useTranslations("agents");
  const resultsT = useTranslations("results");
  const agents = useChatStore((state) => state.agents);
  const handbook = useChatStore((state) => state.handbook);
  const visibleAgents = AGENT_META.filter((agent) => agents[agent.name] !== "idle");

  return (
    <div className="space-y-5">
      {visibleAgents.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {visibleAgents.map((agent) => {
            const status = agents[agent.name];
            const StatusIcon = STATUS_ICON[status];
            return (
              <Card key={agent.name}>
                <CardContent className="flex items-center gap-3 p-3">
                  <agent.icon className="h-4 w-4 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold">{agentsT(agent.name)}</p>
                    <p className="text-[0.65rem] text-muted-foreground">{agentsT(status)}</p>
                  </div>
                  <StatusIcon className={`h-4 w-4 ${STATUS_STYLE[status]}`} />
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {handbook && (
        <div className="grid gap-3 sm:grid-cols-3">
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold">{handbook.days.length}</p>
              <p className="text-xs text-muted-foreground">{resultsT("days")}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold">{handbook.hotels.length}</p>
              <p className="text-xs text-muted-foreground">{agentsT("HotelsAgent")}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold">
                {formatCurrency(
                  handbook.budget_total,
                  handbook.budget_base_currency ?? "USD",
                  {},
                  localeTag(locale),
                )}
              </p>
              <p className="text-xs text-muted-foreground">{resultsT("total")}</p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
