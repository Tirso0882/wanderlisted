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
import { TripWorkspacePanel } from "./trip-workspace-panel";
import { WorkspaceChat } from "./workspace-chat";
import { WorkspaceHeader } from "./workspace-header";

type MobilePane = "chat" | "trip";

export function AtlasWorkspace({ consultationUrl }: { consultationUrl?: string }) {
  const t = useTranslations();
  const [mobilePane, setMobilePane] = useState<MobilePane>("chat");
  const [historyOpen, setHistoryOpen] = useState(false);

  return (
    <div className="atlas-workspace" data-testid="atlas-workspace">
      <WorkspaceHeader onOpenHistory={() => setHistoryOpen(true)} />
      <div className="atlas-workspace-grid">
        <HistoryPanel className="atlas-history-desktop" />
        <main className={cn("atlas-mobile-pane", mobilePane !== "chat" && "atlas-mobile-hidden")}>
          <WorkspaceChat />
        </main>
        <div className={cn("atlas-mobile-pane", mobilePane !== "trip" && "atlas-mobile-hidden")}>
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
    </div>
  );
}
