"use client";

import { History, Menu, Plus, Save } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { claimSessions } from "@/lib/api/sessions";
import { EmbeddedAccountButton, useAuthState } from "@/lib/auth-context";
import { useChatStore } from "@/stores/chat-store";
import { AtlasLogo } from "./atlas-logo";
import { LocaleSwitcher } from "./locale-switcher";

export function WorkspaceHeader({ onOpenHistory }: { onOpenHistory: () => void }) {
  const t = useTranslations();
  const auth = useAuthState();
  const sessionId = useChatStore((state) => state.sessionId);
  const clearChat = useChatStore((state) => state.clearChat);
  const setErrorKey = useChatStore((state) => state.setErrorKey);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!sessionId || saving) return;
    if (!auth.enabled) {
      onOpenHistory();
      return;
    }
    if (!auth.isSignedIn) {
      auth.openSignIn();
      return;
    }
    setSaving(true);
    setErrorKey(null);
    try {
      await claimSessions([sessionId]);
      setSaved(true);
    } catch {
      setErrorKey("save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <header className="atlas-header">
      <a href="#atlas-chat" className="atlas-skip-link">
        {t("a11y.skipToChat")}
      </a>
      <button
        type="button"
        className="atlas-mobile-menu"
        onClick={onOpenHistory}
        aria-label={t("a11y.openHistory")}
      >
        <Menu className="h-5 w-5" />
      </button>
      <AtlasLogo />
      <span className="atlas-header-tagline">{t("brand.tagline")}</span>
      <div className="atlas-header-actions">
        <button
          type="button"
          className="atlas-header-button atlas-history-button"
          onClick={onOpenHistory}
        >
          <History className="h-4 w-4" /> {t("nav.history")}
        </button>
        <button
          type="button"
          className="atlas-header-button"
          onClick={() => {
            clearChat();
            setSaved(false);
          }}
        >
          <Plus className="h-4 w-4" /> <span>{t("nav.newTrip")}</span>
        </button>
        <button
          type="button"
          className="atlas-header-button atlas-save-button"
          disabled={!sessionId || saving}
          onClick={() => void save()}
        >
          <Save className="h-4 w-4" />
          <span>{saved ? t("nav.saved") : t("nav.save")}</span>
        </button>
        <LocaleSwitcher compact />
        {auth.enabled && !auth.isSignedIn && (
          <button type="button" className="atlas-sign-in" onClick={auth.openSignIn}>
            {t("nav.signIn")}
          </button>
        )}
        <EmbeddedAccountButton label={t("auth.signedIn")} />
      </div>
    </header>
  );
}
