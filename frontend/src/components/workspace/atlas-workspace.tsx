"use client";

import { MessageCircle, Route } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { HistoryPanel } from "./history-panel";
import {
  PrototypeSwitcher,
  type PrototypeVariant,
} from "./prototype-switcher";
import { TripWorkspacePanel } from "./trip-workspace-panel";
import { WorkspaceChat } from "./workspace-chat";
import { WorkspaceHeader } from "./workspace-header";

type MobilePane = "chat" | "trip";

// Three variants of the live chat workspace, switchable via ?variant= on the existing route.
export function AtlasWorkspace({
  consultationUrl,
  prototypeVariant = "A",
}: {
  consultationUrl?: string;
  prototypeVariant?: PrototypeVariant;
}) {
  const t = useTranslations();
  const [mobilePane, setMobilePane] = useState<MobilePane>("chat");
  const [historyOpen, setHistoryOpen] = useState(false);

  return (
    <div
      className={`atlas-workspace atlas-prototype-${prototypeVariant.toLowerCase()}`}
      data-testid="atlas-workspace"
      data-prototype-variant={prototypeVariant}
    >
      <WorkspaceHeader onOpenHistory={() => setHistoryOpen(true)} />
      <div className="atlas-workspace-grid">
        {prototypeVariant !== "C" && (
          <HistoryPanel className="atlas-history-desktop atlas-prototype-history" />
        )}
        <main
          className={cn(
            "atlas-mobile-pane atlas-prototype-chat",
            mobilePane !== "chat" && "atlas-mobile-hidden",
          )}
        >
          <WorkspaceChat />
        </main>
        <div
          className={cn(
            "atlas-mobile-pane atlas-prototype-trip",
            mobilePane !== "trip" && "atlas-mobile-hidden",
          )}
        >
          <TripWorkspacePanel consultationUrl={consultationUrl} />
        </div>
      </div>

      <nav className="atlas-mobile-nav" aria-label={t("a11y.mobileNavigation")}>
        <button
          type="button"
          aria-current={mobilePane === "chat" ? "page" : undefined}
          onClick={() => setMobilePane("chat")}
        >
          <MessageCircle /> {t("nav.chat")}
        </button>
        <button
          type="button"
          aria-current={mobilePane === "trip" ? "page" : undefined}
          onClick={() => setMobilePane("trip")}
        >
          <Route /> {t("nav.trip")}
        </button>
      </nav>

      <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
        <SheetContent side="left" showCloseButton={false} className="atlas-history-sheet">
          <SheetHeader className="sr-only">
            <SheetTitle>{t("history.title")}</SheetTitle>
            <SheetDescription>{t("history.subtitle")}</SheetDescription>
          </SheetHeader>
          <HistoryPanel onClose={() => setHistoryOpen(false)} />
        </SheetContent>
      </Sheet>

      <PrototypeSwitcher current={prototypeVariant} />
    </div>
  );
}
