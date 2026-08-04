import { AtlasWorkspace } from "@/components/workspace";
import { LegacyChatPage } from "@/components/views/legacy-chat-page";
import { getRequestLocale } from "@/i18n/server";

function enabled(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

function configuredConsultationUrl(value: string | undefined): string | undefined {
  if (!value?.trim()) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : undefined;
  } catch {
    return undefined;
  }
}

export default async function ChatPage() {
  if (!enabled(process.env.CHAT_UI_V2_ENABLED)) return <LegacyChatPage />;
  const locale = await getRequestLocale();
  const consultationUrl = configuredConsultationUrl(
    locale === "pl"
      ? process.env.CONSULTATION_URL_PL
      : process.env.CONSULTATION_URL_EN,
  );
  return <AtlasWorkspace consultationUrl={consultationUrl} />;
}
