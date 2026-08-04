"use client";

import { ClerkProvider } from "@clerk/nextjs";
import { enUS, plPL } from "@clerk/localizations";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { LocalePreferenceSync } from "@/i18n/locale-preference-sync";
import type { AppLocale } from "@/i18n/config";
import { AuthBridge } from "@/lib/auth-context";
import { ThemeProvider } from "./theme-provider";
import { useState } from "react";

type ProvidersProps = {
  children: React.ReactNode;
  locale: AppLocale;
  messages: AbstractIntlMessages;
  clerkEnabled: boolean;
  clerkPublishableKey?: string;
};

function ApplicationProviders({
  children,
  clerkEnabled,
}: Pick<ProvidersProps, "children" | "clerkEnabled">) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthBridge enabled={clerkEnabled}>
        <ThemeProvider>
          <TooltipProvider delay={300}>
            <LocalePreferenceSync />
            {children}
          </TooltipProvider>
        </ThemeProvider>
      </AuthBridge>
    </QueryClientProvider>
  );
}

export function Providers({
  children,
  locale,
  messages,
  clerkEnabled,
  clerkPublishableKey,
}: ProvidersProps) {
  const application = (
    <NextIntlClientProvider locale={locale} messages={messages} timeZone="Europe/Warsaw">
      <ApplicationProviders clerkEnabled={clerkEnabled}>
        {children}
      </ApplicationProviders>
    </NextIntlClientProvider>
  );

  if (!clerkEnabled || !clerkPublishableKey) return application;

  return (
    <ClerkProvider
      publishableKey={clerkPublishableKey}
      localization={locale === "pl" ? plPL : enUS}
      appearance={{
        variables: {
          colorPrimary: "#ef765c",
          borderRadius: "0.875rem",
        },
      }}
    >
      {application}
    </ClerkProvider>
  );
}
