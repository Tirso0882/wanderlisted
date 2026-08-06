"use client";

import {
  Shield,
  Globe,
  Heart,
  Phone,
  AlertTriangle,
  Languages,
  Clock,
  Coins,
  CloudSun,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { localeTag, type AppLocale } from "@/i18n/config";
import type {
  SafetyInfo,
  SafetyWarning,
  CultureGuide,
  DayWeather,
  TravelReadinessReport,
} from "@/lib/types";

const ADVISORY_COLORS: Record<string, string> = {
  unknown: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  green: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  yellow:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  orange:
    "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
  red: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
};

const ADVISORY_LABELS = {
  unknown: "advisory.unknown",
  green: "advisory.green",
  yellow: "advisory.yellow",
  orange: "advisory.orange",
  red: "advisory.red",
} as const;

const CONSTRAINT_LABELS = {
  safety: "constraint.safety",
  entry: "constraint.entry",
  health: "constraint.health",
  weather: "constraint.weather",
  culture: "constraint.culture",
} as const;

function formatCalendarDate(value: string, locale: AppLocale): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return new Intl.DateTimeFormat(localeTag(locale), {
    day: "numeric",
    month: "short",
  }).format(date);
}

function SafetyCard({ safety }: { safety: SafetyInfo }) {
  const t = useTranslations("destinationDetails");
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Shield className="h-4 w-4" />
            {t("safetyTitle")}
          </CardTitle>
          <Badge
            className={
              ADVISORY_COLORS[safety.advisory_level] ?? ADVISORY_COLORS.unknown
            }
          >
            {t(ADVISORY_LABELS[safety.advisory_level])}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {safety.advisory_summary && (
          <p className="text-sm text-muted-foreground">
            {safety.advisory_summary}
          </p>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          {/* Visa */}
          {safety.visa_requirements && (
            <div className="space-y-1">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Globe className="h-3 w-3" /> {t("visa")}
              </h4>
              <p className="text-sm">{safety.visa_requirements}</p>
            </div>
          )}

          {/* Languages */}
          {safety.languages.length > 0 && (
            <div className="space-y-1">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Languages className="h-3 w-3" /> {t("languages")}
              </h4>
              <p className="text-sm">{safety.languages.join(", ")}</p>
            </div>
          )}

          {/* Currency */}
          <div className="space-y-1">
            <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <Coins className="h-3 w-3" /> {t("currency")}
            </h4>
            <p className="text-sm">
              {safety.currency_name} ({safety.currency_symbol}{" "}
              {safety.currency_code})
            </p>
          </div>

          {/* Timezone */}
          {safety.timezones.length > 0 && (
            <div className="space-y-1">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Clock className="h-3 w-3" /> {t("timezone")}
              </h4>
              <p className="text-sm">{safety.timezones.join(", ")}</p>
            </div>
          )}
        </div>

        {/* Emergency numbers */}
        {Object.keys(safety.emergency_numbers).length > 0 && (
          <>
            <Separator />
            <div className="space-y-1">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Phone className="h-3 w-3" /> {t("emergencyNumbers")}
              </h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(safety.emergency_numbers).map(
                  ([service, number]) => (
                    <Badge key={service} variant="outline" className="text-xs">
                      {service}: {number}
                    </Badge>
                  ),
                )}
              </div>
            </div>
          </>
        )}

        {/* Health requirements */}
        {safety.health_requirements.length > 0 && (
          <>
            <Separator />
            <div className="space-y-1">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Heart className="h-3 w-3" /> {t("healthRequirements")}
              </h4>
              <ul className="space-y-0.5 text-sm text-muted-foreground">
                {safety.health_requirements.map((req, i) => (
                  <li key={i}>• {req}</li>
                ))}
              </ul>
            </div>
          </>
        )}

        {/* Safety tips */}
        {safety.safety_tips.length > 0 && (
          <>
            <Separator />
            <div className="space-y-1">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <AlertTriangle className="h-3 w-3" /> {t("safetyTips")}
              </h4>
              <ul className="space-y-0.5 text-sm text-muted-foreground">
                {safety.safety_tips.map((tip, i) => (
                  <li key={i}>• {tip}</li>
                ))}
              </ul>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function CultureCard({ culture }: { culture: CultureGuide }) {
  const t = useTranslations("destinationDetails");
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">{t("cultureTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Useful phrases */}
        {culture.phrases.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t("usefulPhrases")}
            </h4>
            <div className="grid gap-1 sm:grid-cols-2">
              {culture.phrases.map((phrase, i) => {
                const entries = Object.entries(phrase);
                return entries.map(([key, val]) => (
                  <div
                    key={`${i}-${key}`}
                    className="flex justify-between rounded-md bg-muted/50 px-3 py-1.5 text-sm"
                  >
                    <span className="font-medium">{key}</span>
                    <span className="text-muted-foreground">{val}</span>
                  </div>
                ));
              })}
            </div>
          </div>
        )}

        {/* Tipping */}
        {culture.tipping_guide && (
          <div className="space-y-1">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t("tipping")}
            </h4>
            <p className="text-sm text-muted-foreground">
              {culture.tipping_guide}
            </p>
          </div>
        )}

        {/* Etiquette tips */}
        {culture.etiquette_tips.length > 0 && (
          <div className="space-y-1">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t("etiquette")}
            </h4>
            <ul className="space-y-0.5 text-sm text-muted-foreground">
              {culture.etiquette_tips.map((tip, i) => (
                <li key={i}>• {tip}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Dining customs */}
        {culture.dining_customs.length > 0 && (
          <div className="space-y-1">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {t("diningCustoms")}
            </h4>
            <ul className="space-y-0.5 text-sm text-muted-foreground">
              {culture.dining_customs.map((custom, i) => (
                <li key={i}>• {custom}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function DestinationTab({
  safety,
  safetyWarning = null,
  culture,
  weather = [],
  readiness = null,
}: {
  safety: SafetyInfo | null;
  safetyWarning?: SafetyWarning | null;
  culture: CultureGuide | null;
  weather?: DayWeather[];
  readiness?: TravelReadinessReport | null;
}) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("destinationDetails");
  const numberFormatter = new Intl.NumberFormat(localeTag(locale), {
    maximumFractionDigits: 0,
  });
  if (!safety && !safetyWarning && !culture && weather.length === 0 && !readiness) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <MapPin className="mb-3 h-8 w-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">
          {t("empty")}
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {safetyWarning && (
        <div
          role="alert"
          className={`flex gap-3 rounded-md border p-4 lg:col-span-2 ${
            safetyWarning.advisory_level === "red"
              ? "border-red-300 bg-red-50 text-red-950 dark:border-red-800 dark:bg-red-950/30 dark:text-red-100"
              : "border-orange-300 bg-orange-50 text-orange-950 dark:border-orange-800 dark:bg-orange-950/30 dark:text-orange-100"
          }`}
        >
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <div className="space-y-1">
            <p className="text-sm font-semibold">{t("warningTitle")}</p>
            <p className="text-sm">{safetyWarning.message}</p>
          </div>
        </div>
      )}
      {readiness?.summary && (
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">{t("summaryTitle")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{readiness.summary}</p>
          </CardContent>
        </Card>
      )}
      {safety && <SafetyCard safety={safety} />}
      {culture && <CultureCard culture={culture} />}
      {weather.length > 0 && (
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <CloudSun className="h-4 w-4" /> {t("forecastTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {weather.map((day) => (
              <div key={day.date} className="rounded-md bg-muted/50 p-3 text-sm">
                <div className="font-medium">{formatCalendarDate(day.date, locale)}</div>
                <div className="text-muted-foreground">{day.condition}</div>
                <div>
                  {numberFormatter.format(Math.round(day.temp_low_c))}–
                  {numberFormatter.format(Math.round(day.temp_high_c))}°C · {t("rain", {
                    percent: numberFormatter.format(day.rain_probability_pct),
                  })}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
      {readiness && readiness.planning_constraints.length > 0 && (
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">{t("planningConstraints")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {readiness.planning_constraints.map((constraint, index) => (
              <div key={`${constraint.category}-${index}`} className="flex gap-2 text-sm">
                <Badge variant="outline">{t(CONSTRAINT_LABELS[constraint.category])}</Badge>
                <span>{constraint.summary}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
      {readiness && readiness.limitations.length > 0 && (
        <Card className="border-amber-300 lg:col-span-2 dark:border-amber-800">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <AlertTriangle className="h-4 w-4 text-amber-600" /> {t("verificationLimits")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm text-muted-foreground">
              {readiness.limitations.map((item, index) => (
                <li key={index}>• {item}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function MapPin(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}
