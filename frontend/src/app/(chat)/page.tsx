import { AtlasWorkspace } from "@/components/workspace";
import type { PrototypeVariant } from "@/components/workspace/prototype-switcher";
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

function prototypeVariant(value: string | string[] | undefined): PrototypeVariant {
  const candidate = Array.isArray(value) ? value[0] : value;
  return candidate === "B" || candidate === "C" ? candidate : "A";
}

export default async function ChatPage({
  searchParams,
}: {
  searchParams: Promise<{ variant?: string | string[] }>;
}) {
  const locale = await getRequestLocale();
  const query = await searchParams;
  const consultationUrl = configuredConsultationUrl(
    locale === "pl"
      ? process.env.CONSULTATION_URL_PL
      : process.env.CONSULTATION_URL_EN,
  );
  return (
    <AtlasWorkspace
      consultationUrl={consultationUrl}
      prototypeVariant={
        process.env.NODE_ENV === "production"
          ? "A"
          : prototypeVariant(query.variant)
      }
    />
  );
}
