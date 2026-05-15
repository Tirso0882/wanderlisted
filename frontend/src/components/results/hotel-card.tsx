"use client";

import { Star, MapPin, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { HotelOption } from "@/lib/types";

export function HotelCard({ hotel }: { hotel: HotelOption }) {
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
            ${hotel.price_per_night_usd.toLocaleString()}
            <span className="text-xs font-normal text-muted-foreground">
              /night
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
            {hotel.neighbourhood || "City center"}
          </div>
        </div>

        {/* Details */}
        <div className="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
          <span>Room: {hotel.room_type || "Standard"}</span>
          <span>Bed: {hotel.bed_type || "—"}</span>
          <span>Check-in: {hotel.check_in}</span>
          <span>Check-out: {hotel.check_out}</span>
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
            Total: ${hotel.total_price_usd.toLocaleString()}
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
              Book <ExternalLink className="h-3 w-3" />
            </a>
          )}
          {hotel.google_maps_url && (
            <a
              href={hotel.google_maps_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:underline"
            >
              Map <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
