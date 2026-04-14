"""Quick check of handbook.json content."""

import json

with open("outputs/handbook.json") as f:
    h = json.load(f)

print(f"Trip title: {h.get('trip_title', '')}")
print(f"Destinations: {h.get('destinations', [])}")
print(f"Flights: {len(h.get('flights', []))} options")
print(f"Hotels: {len(h.get('hotels', []))} options")
print(f"Days: {len(h.get('days', []))} days")

for d in h.get("days", []):
    tb = d.get("time_blocks", [])
    acts = sum(len(b.get("activities", [])) for b in tb)
    rest = sum(1 for b in tb if b.get("restaurant"))
    has_route = bool(d.get("route_map_url", ""))
    print(
        f"  Day {d.get('day_number')}: {len(tb)} blocks, {acts} activities, {rest} restaurants, route_map={has_route}"
    )

print(f"Safety advisory: {h.get('safety', {}).get('advisory_summary', '')[:100]}")
print(f"Culture phrases: {len(h.get('culture', {}).get('phrases', []))}")
print(f"Packing items: {len(h.get('packing', []))}")
print(f"Budget total: {h.get('budget_total', 0)}")

for hotel in h.get("hotels", []):
    photos = hotel.get("photo_urls", [])
    embed = bool(hotel.get("map_embed_url", ""))
    print(f"  Hotel '{hotel.get('name', '')}': {len(photos)} photos, map_embed={embed}")

# Check activity photos
photo_count = 0
for d in h.get("days", []):
    for tb in d.get("time_blocks", []):
        for act in tb.get("activities", []):
            if act.get("photo_urls"):
                photo_count += 1
        r = tb.get("restaurant")
        if r and r.get("photo_urls"):
            photo_count += 1
print(f"Activities/restaurants with photos: {photo_count}")
