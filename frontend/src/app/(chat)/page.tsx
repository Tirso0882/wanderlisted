import { AtlasWorkspace } from "@/components/workspace";
import { getRequestLocale } from "@/i18n/server";

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
  const locale = await getRequestLocale();
  const consultationUrl = configuredConsultationUrl(
    locale === "pl"
      ? process.env.CONSULTATION_URL_PL
      : process.env.CONSULTATION_URL_EN,
  );
  return <AtlasWorkspace consultationUrl={consultationUrl} />;
}
