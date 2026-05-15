"use client";

import { Star, Clock, MapPin, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PlaceCard } from "@/lib/types";

interface PlaceCardComponentProps {
  place: PlaceCard;
  variant?: "activity" | "restaurant";
}

export function PlaceCardComponent({
  place,
  variant = "activity",
}: PlaceCardComponentProps) {
  const photoUrl = place.photo_urls?.[0];

  return (
    <Card className="overflow-hidden">
      {photoUrl && (
        <div className="relative aspect-[16/9] w-full overflow-hidden">
          <img
            src={photoUrl}
            alt={place.name}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        </div>
      )}

      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-sm leading-tight">{place.name}</CardTitle>
            <p className="text-xs text-muted-foreground">{place.category}</p>
          </div>
          {place.estimated_cost_usd > 0 && (
            <span className="shrink-0 text-sm font-bold text-primary">
              ${place.estimated_cost_usd}
            </span>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-2">
        {/* Rating + Reviews */}
        <div className="flex items-center gap-3">
          {place.rating !== null && (
            <div className="flex items-center gap-1">
              <Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />
              <span className="text-xs font-medium">{place.rating.toFixed(1)}</span>
              {place.review_count > 0 && (
                <span className="text-xs text-muted-foreground">
                  ({place.review_count.toLocaleString()})
                </span>
              )}
            </div>
          )}
          {place.price_level && (
            <Badge variant="outline" className="text-xs">
              {place.price_level}
            </Badge>
          )}
          {place.estimated_duration_minutes > 0 && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              {place.estimated_duration_minutes}m
            </div>
          )}
        </div>

        {/* Description excerpt */}
        {place.description && (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {place.description}
          </p>
        )}

        {/* Address */}
        {place.address && (
          <div className="flex items-start gap-1 text-xs text-muted-foreground">
            <MapPin className="mt-0.5 h-3 w-3 shrink-0" />
            <span className="line-clamp-1">{place.address}</span>
          </div>
        )}

        {/* Links */}
        <div className="flex flex-wrap gap-2">
          {place.google_maps_url && (
            <a
              href={place.google_maps_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              {variant === "restaurant" ? "Directions" : "Map"}{" "}
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
          {place.website_url && (
            <a
              href={place.website_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"
            >
              Website <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
