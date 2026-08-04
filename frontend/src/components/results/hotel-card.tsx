"use client";

import { Star, MapPin, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatCurrency } from "@/lib/format-currency";
import type { HotelOption } from "@/lib/types";
import { useLocale, useTranslations } from "next-intl";
import { localeTag, type AppLocale } from "@/i18n/config";

function formatCalendarDate(value: string, locale: AppLocale): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return new Intl.DateTimeFormat(localeTag(locale), {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

export function HotelCard({ hotel }: { hotel: HotelOption }) {
  const locale = useLocale() as AppLocale;
  const t = useTranslations("cards");
  const resultsT = useTranslations("results");
  const photoUrl = hotel.photo_urls?.[0];

  return (
    <Card className="overflow-hidden">
      {/* Photo */}
      {photoUrl && (
        <div className="relative aspect-[16/9] w-full overflow-hidden">
          <img
            src={photoUrl}
            alt={hotel.name}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        </div>
      )}

      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm leading-tight">{hotel.name}</CardTitle>
          <span className="shrink-0 text-lg font-bold text-primary">
            {formatCurrency(hotel.price_per_night_usd, "USD", {}, localeTag(locale))}
            <span className="text-xs font-normal text-muted-foreground">
              /{t("night")}
            </span>
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Stars + Neighbourhood */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-0.5">
            {Array.from({ length: hotel.star_rating }, (_, i) => (
              <Star
                key={i}
                className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400"
              />
            ))}
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3" />
            {hotel.neighbourhood || t("cityCentre")}
          </div>
        </div>

        {/* Details */}
        <div className="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
          <span>{t("room")}: {hotel.room_type || t("standard")}</span>
          <span>{t("bed")}: {hotel.bed_type || "—"}</span>
          <span>{t("checkIn")}: {formatCalendarDate(hotel.check_in, locale)}</span>
          <span>{t("checkOut")}: {formatCalendarDate(hotel.check_out, locale)}</span>
        </div>

        {/* Amenities */}
        {hotel.amenities.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {hotel.amenities.slice(0, 5).map((amenity) => (
              <Badge key={amenity} variant="secondary" className="text-xs">
                {amenity}
              </Badge>
            ))}
            {hotel.amenities.length > 5 && (
              <Badge variant="outline" className="text-xs">
                +{hotel.amenities.length - 5}
              </Badge>
            )}
          </div>
        )}

        {/* Total + Cancellation */}
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium">
            {resultsT("total")}: {formatCurrency(hotel.total_price_usd, "USD", {}, localeTag(locale))}
          </span>
          {hotel.cancellation_policy && (
            <span className="text-muted-foreground">
              {hotel.cancellation_policy}
            </span>
          )}
        </div>

        {/* Links */}
        <div className="flex flex-wrap gap-2">
          {hotel.booking_url && (
            <a
              href={hotel.booking_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              {t("book")} <ExternalLink className="h-3 w-3" />
            </a>
          )}
          {hotel.google_maps_url && (
            <a
              href={hotel.google_maps_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"
            >
              {t("map")} <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
