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
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { SafetyInfo, CultureGuide } from "@/lib/types";

const ADVISORY_COLORS: Record<string, string> = {
  green: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  yellow:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  orange:
    "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
  red: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
};

function SafetyCard({ safety }: { safety: SafetyInfo }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Shield className="h-4 w-4" />
            Safety & Travel Advisory
          </CardTitle>
          <Badge
            className={
              ADVISORY_COLORS[safety.advisory_level] ?? ADVISORY_COLORS.green
            }
          >
            {safety.advisory_level.toUpperCase()}
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
                <Globe className="h-3 w-3" /> Visa
              </h4>
              <p className="text-sm">{safety.visa_requirements}</p>
            </div>
          )}

          {/* Languages */}
          {safety.languages.length > 0 && (
            <div className="space-y-1">
              <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Languages className="h-3 w-3" /> Languages
              </h4>
              <p className="text-sm">{safety.languages.join(", ")}</p>
            </div>
          )}

          {/* Currency */}
          <div className="space-y-1">
            <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <Coins className="h-3 w-3" /> Currency
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
                <Clock className="h-3 w-3" /> Timezone
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
                <Phone className="h-3 w-3" /> Emergency Numbers
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
                <Heart className="h-3 w-3" /> Health Requirements
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
                <AlertTriangle className="h-3 w-3" /> Safety Tips
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
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Culture & Etiquette</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Useful phrases */}
        {culture.phrases.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Useful Phrases
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
              Tipping
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
              Etiquette
            </h4>
            <ul className="space-y-0.5 text-sm text-muted-foreground">
              {culture.etiquette_tips.map((tip, i) => (
                <li key={i}>• {tip}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Food specialties */}
        {culture.food_specialties.length > 0 && (
          <div className="space-y-1">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Must-Try Foods
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {culture.food_specialties.map((food) => (
                <Badge key={food} variant="secondary" className="text-xs">
                  {food}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Dining customs */}
        {culture.dining_customs.length > 0 && (
          <div className="space-y-1">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Dining Customs
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
  culture,
}: {
  safety: SafetyInfo | null;
  culture: CultureGuide | null;
}) {
  if (!safety && !culture) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <MapPin className="mb-3 h-8 w-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">
          Destination research will appear here once the agent completes.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {safety && <SafetyCard safety={safety} />}
      {culture && <CultureCard culture={culture} />}
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
