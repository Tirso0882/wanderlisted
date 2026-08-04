"use client";

import { Clock3, LogIn, RefreshCw, Trash2, Upload, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { localeTag, type AppLocale } from "@/i18n/config";
import {
  browserSessionIds,
  claimSessions,
  deleteSession,
  fetchSessionSnapshot,
  fetchSessions,
} from "@/lib/api/sessions";
import { useAuthState } from "@/lib/auth-context";
import type { SessionSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";

type HistoryErrorKey = "loadHistory" | "snapshot" | "delete" | "save";

export function HistoryPanel({
  onClose,
  className,
}: {
  onClose?: () => void;
  className?: string;
}) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations();
  const auth = useAuthState();
  const currentSessionId = useChatStore((state) => state.sessionId);
  const restoreSnapshot = useChatStore((state) => state.restoreSnapshot);
  const clearChat = useChatStore((state) => state.clearChat);
  const [items, setItems] = useState<SessionSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorKey, setErrorKey] = useState<HistoryErrorKey | null>(null);
  const [imported, setImported] = useState(false);

  const load = useCallback(
    async (cursor?: string | null) => {
      if (!auth.enabled || !auth.isSignedIn) return;
      setLoading(true);
      setErrorKey(null);
      try {
        const page = await fetchSessions(cursor);
        setItems((current) => (cursor ? [...current, ...page.items] : page.items));
        setNextCursor(page.next_cursor);
      } catch {
        setErrorKey("loadHistory");
      } finally {
        setLoading(false);
      }
    },
    [auth.enabled, auth.isSignedIn],
  );

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
  }, [load]);

  const restore = async (session: SessionSummary) => {
    setErrorKey(null);
    try {
      const snapshot = await fetchSessionSnapshot(session.id);
      restoreSnapshot(session.id, snapshot);
      onClose?.();
    } catch {
      setErrorKey("snapshot");
    }
  };

  const remove = async (session: SessionSummary) => {
    if (!window.confirm(t("history.deleteConfirm"))) return;
    try {
      await deleteSession(session.id);
      setItems((current) => current.filter((item) => item.id !== session.id));
      if (currentSessionId === session.id) clearChat();
    } catch {
      setErrorKey("delete");
    }
  };

  const importBrowserChats = async () => {
    const sessionIds = browserSessionIds();
    if (!sessionIds.length) return;
    try {
      await claimSessions(sessionIds);
      setImported(true);
      await load();
    } catch {
      setErrorKey("save");
    }
  };

  return (
    <aside className={cn("atlas-history-panel", className)} aria-label={t("history.title")}>
      <div className="atlas-history-heading">
        <div>
          <h2>{t("history.title")}</h2>
          <p>{t("history.subtitle")}</p>
        </div>
        {onClose && (
          <button type="button" onClick={onClose} aria-label={t("history.close")}>
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {!auth.isLoaded ? (
        <p className="atlas-history-message">{t("auth.loading")}</p>
      ) : !auth.enabled ? (
        <div className="atlas-auth-gate">
          <Clock3 className="h-5 w-5" />
          <p>{t("auth.unavailable")}</p>
        </div>
      ) : !auth.isSignedIn ? (
        <div className="atlas-auth-gate">
          <LogIn className="h-5 w-5" />
          <h3>{t("history.authTitle")}</h3>
          <p>{t("history.authBody")}</p>
          <button type="button" className="atlas-primary-button" onClick={auth.openSignIn}>
            {t("nav.signIn")}
          </button>
        </div>
      ) : (
        <>
          <button
            type="button"
            className="atlas-import-button"
            onClick={() => void importBrowserChats()}
          >
            <Upload className="h-4 w-4" /> {t("history.import")}
          </button>
          {imported && <p className="atlas-success-message">{t("history.imported")}</p>}
          {errorKey && <p className="atlas-form-error">{t(`errors.${errorKey}`)}</p>}
          <div className="atlas-history-list">
            {!loading && items.length === 0 && (
              <div className="atlas-history-empty">
                <p>{t("history.empty")}</p>
                <span>{t("history.emptyHint")}</span>
              </div>
            )}
            {items.map((session) => (
              <article
                key={session.id}
                className={cn(
                  "atlas-history-item",
                  currentSessionId === session.id && "atlas-history-item-active",
                )}
              >
                <button
                  type="button"
                  className="atlas-history-open"
                  onClick={() => void restore(session)}
                  aria-label={`${t("history.open")}: ${session.title}`}
                >
                  <span className="atlas-history-title">{session.title}</span>
                  <span>
                    {t("history.updated", {
                      date: new Intl.DateTimeFormat(localeTag(locale), {
                        day: "numeric",
                        month: "short",
                      }).format(new Date(session.updated_at)),
                    })}
                  </span>
                  <span>{t("history.messages", { count: session.message_count })}</span>
                  {currentSessionId === session.id && (
                    <strong>{t("history.current")}</strong>
                  )}
                </button>
                <button
                  type="button"
                  className="atlas-history-delete"
                  onClick={() => void remove(session)}
                  aria-label={`${t("history.delete")}: ${session.title}`}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </article>
            ))}
          </div>
          {loading && <p className="atlas-history-message">{t("history.loading")}</p>}
          {nextCursor && !loading && (
            <button
              type="button"
              className="atlas-load-more"
              onClick={() => void load(nextCursor)}
            >
              <RefreshCw className="h-3.5 w-3.5" /> {t("history.loadMore")}
            </button>
          )}
        </>
      )}
    </aside>
  );
}
