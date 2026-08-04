import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import { getRequestMessages } from "@/i18n/server";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const { messages } = await getRequestMessages();
  return {
    title: messages.meta.title,
    description: messages.meta.description,
  };
}

function enabled(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const { locale, messages } = await getRequestMessages();
  const clerkPublishableKey = (
    process.env.CLERK_PUBLISHABLE_KEY ??
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
  )?.trim();
  const clerkEnabled =
    enabled(process.env.CLERK_ENABLED) &&
    Boolean(clerkPublishableKey) &&
    Boolean(process.env.CLERK_SECRET_KEY?.trim());

  return (
    <html
      lang={locale === "pl" ? "pl-PL" : "en-GB"}
      suppressHydrationWarning
      className="h-full antialiased"
    >
      <body className="h-full flex flex-col overflow-hidden">
        <Providers
          locale={locale}
          messages={messages}
          clerkEnabled={clerkEnabled}
          clerkPublishableKey={clerkPublishableKey}
        >
          {children}
        </Providers>
      </body>
    </html>
  );
}
