// TypeScript interfaces mirroring src/models/itinerary.py

import type {
  AdvisoryLevel,
  CabinClass,
  DayPeriod,
  PackingCategory,
  TransitMode,
} from "./enums";

// ── Flights ─────────────────────────────────────────────────────────────

export interface FlightSegment {
  carrier: string;
  flight_number: string;
  departure_airport: string;
  arrival_airport: string;
  departure_time: string;
  arrival_time: string;
  duration_minutes: number;
  cabin_class: CabinClass;
  stops: number;
  origin_country: string;
  destination_country: string;
}

export interface FlightOption {
  outbound: FlightSegment[];
  inbound: FlightSegment[];
  total_price_usd: number;
  currency: string;
  booking_url: string;
  skyscanner_url: string;
  google_flights_url: string;
}

// ── Hotels ──────────────────────────────────────────────────────────────

export interface HotelOption {
  name: string;
  star_rating: number;
  neighbourhood: string;
  price_per_night_usd: number;
  total_price_usd: number;
  room_type: string;
  bed_type: string;
  check_in: string;
  check_out: string;
  amenities: string[];
  cancellation_policy: string;
  booking_url: string;
  booking_com_url: string;
  google_hotels_url: string;
  latitude: number;
  longitude: number;
  photo_urls: string[];
  google_maps_url: string;
  website_url: string;
  description: string;
  distance_from_center_km: number;
  nearby_attractions: string[];
  map_embed_url: string;
}

// ── Places ──────────────────────────────────────────────────────────────

export interface PlaceCard {
  name: string;
  category: string;
  rating: number | null;
  review_count: number;
  price_level: string;
  address: string;
  description: string;
  website_url: string;
  google_maps_url: string;
  photo_urls: string[];
  opening_hours: string[];
  latitude: number;
  longitude: number;
  estimated_cost_usd: number;
  estimated_duration_minutes: number;
}

// ── Transit ─────────────────────────────────────────────────────────────

export interface TransitStep {
  mode: TransitMode;
  from_place: string;
  to_place: string;
  distance_text: string;
  duration_text: string;
  transit_line: string;
  instructions: string;
  booking_url: string;
  fare_estimate_usd: number;
}

// ── Weather ─────────────────────────────────────────────────────────────

export interface DayWeather {
  date: string;
  condition: string;
  emoji: string;
  temp_low_c: number;
  temp_high_c: number;
  rain_probability_pct: number;
  packing_tip: string;
}

// ── Day Plan ────────────────────────────────────────────────────────────

export interface TimeBlock {
  period: DayPeriod;
  activities: PlaceCard[];
  restaurant: PlaceCard | null;
  transit: TransitStep[];
  subtotal_usd: number;
}

export interface DayPlan {
  day_number: number;
  date: string;
  city: string;
  weather: DayWeather | null;
  time_blocks: TimeBlock[];
  cultural_tip: string;
  daily_cost_usd: number;
  walking_km: number;
  route_map_url: string;
}

// ── Safety ──────────────────────────────────────────────────────────────

export interface SafetyInfo {
  advisory_level: AdvisoryLevel;
  advisory_level_num: number;
  advisory_summary: string;
  visa_requirements: string;
  health_requirements: string[];
  emergency_numbers: Record<string, string>;
  languages: string[];
  currency_name: string;
  currency_symbol: string;
  currency_code: string;
  timezones: string[];
  seasonal_risks: string[];
  natural_hazards: string[];
  safety_tips: string[];
  embassy_info: string;
}

// ── Culture ─────────────────────────────────────────────────────────────

export interface CultureGuide {
  phrases: Record<string, string>[];
  etiquette_tips: string[];
  tipping_guide: string;
  dining_customs: string[];
  religious_customs: string[];
  dress_code_notes: string[];
  festivals: Record<string, string>[];
  food_specialties: string[];
  local_customs: Record<string, string>[];
  music_and_arts: string[];
  etiquette_cards: Record<string, string>[];
}

// ── Currency Exchange ───────────────────────────────────────────────────

export interface CurrencyExchangeLocation {
  name: string;
  address: string;
  google_maps_url: string;
  rating: number | null;
  notes: string;
}

// ── Local Tips ──────────────────────────────────────────────────────────

export interface LocalTipsApps {
  must_have_apps: Record<string, string>[];
  sim_card_info: string;
  wifi_info: string;
  transport_cards: Record<string, string>[];
  power_adapter: string;
  useful_websites: Record<string, string>[];
}

// ── Emergency ───────────────────────────────────────────────────────────

export interface EmergencyInfo {
  hospitals: PlaceCard[];
  pharmacies: PlaceCard[];
  insurance_notes: string;
  medical_phrases: Record<string, string>[];
  vaccination_tips: string[];
}

// ── Packing ─────────────────────────────────────────────────────────────

export interface PackingItem {
  item: string;
  reason: string;
  category: PackingCategory;
  essential: boolean;
  weather_context: string;
  activity_context: string;
}

export interface PlanningConstraint {
  category: "safety" | "entry" | "health" | "weather" | "culture";
  severity: "info" | "warning" | "blocking";
  summary: string;
  destination: string;
  affected_dates: string[];
  source_ids: string[];
}

export interface ReadinessSource {
  id: string;
  title: string;
  url: string;
  domain: string;
  snippet: string;
  relevance: number;
  query: string;
  topic: "culture" | "safety" | "weather" | "visa" | "health" | "practical";
  is_official: boolean;
  published_at: string | null;
  retrieved_at: string;
}

export interface TravelReadinessReport {
  destinations: string[];
  intent: string;
  summary: string;
  safety: SafetyInfo;
  culture: CultureGuide;
  weather: DayWeather[];
  weather_summary: string[];
  planning_constraints: PlanningConstraint[];
  packing_constraints: PackingItem[];
  sources: ReadinessSource[];
  citations: Record<string, string[]>;
  limitations: string[];
  generated_at: string;
}

// ── Budget ──────────────────────────────────────────────────────────────

export interface BudgetBreakdown {
  schema_version?: number;
  flights: number;
  accommodation: number;
  transport: number;
  meals: number;
  activities: number;
  misc: number;
  total: number;
  per_person: number;
  target_budget?: number;
  currency: string;
  summary: string;
  base_currency?: string;
  display_currency?: string;
  display_breakdown?: BudgetAmounts | null;
  line_items?: BudgetLineItem[];
  provenance?: PriceEvidence[];
  non_numeric_evidence?: NonNumericPriceEvidence[];
  conversion_rates?: ConversionRateRecord[];
  conversion_status?: "not_needed" | "complete" | "unavailable";
  coverage_status?: "complete" | "complete_with_estimates" | "partial";
  missing_categories?: BudgetCategory[];
  estimated_categories?: BudgetCategory[];
  assumptions?: string[];
  reconciliation_delta?: number;
  verdict?: "no_target" | "within_budget" | "over_budget" | "unknown";
  remaining_budget?: number | null;
  reserve_recommendation?: number;
  display_reserve_recommendation?: number | null;
  reserve_recommendation_percent?: number;
  contingency_included?: boolean;
  contingency_percent?: number | null;
  display_conversion_available?: boolean;
  request_fingerprint?: string;
}

export type BudgetCategory =
  | "flights"
  | "accommodation"
  | "transport"
  | "meals"
  | "activities"
  | "misc";

export interface BudgetAmounts {
  flights: number;
  accommodation: number;
  transport: number;
  meals: number;
  activities: number;
  misc: number;
  total: number;
  per_person: number;
  target_budget: number;
  remaining_budget: number | null;
  currency: string;
}

export interface BudgetLineItem {
  category: BudgetCategory;
  source_component: string;
  source_id: string;
  source_amount: number;
  source_currency: string;
  quantity?: number;
  applied_multiplier?: number;
  source_total?: number;
  amount_usd: number | null;
  display_amount: number | null;
  display_currency: string;
  scope: "total" | "per_person" | "per_night" | "per_person_day";
  basis: "quoted" | "user_supplied" | "regional_estimate" | "contingency";
  estimated: boolean;
  assumption: string;
  conversion_error?: string;
}

export interface PriceEvidence {
  category: BudgetCategory;
  money: { amount: string | number; currency: string };
  source_component: string;
  source_id: string;
  scope: "total" | "per_person" | "per_night" | "per_person_day";
  basis: "quoted" | "user_supplied" | "regional_estimate" | "contingency";
  selection_status: "candidate" | "selected" | "user_supplied";
  quantity: string | number;
  observed_at?: string | null;
  evidence_text?: string;
}

export interface NonNumericPriceEvidence {
  source_component: string;
  source_id: string;
  category: BudgetCategory | null;
  signal: string;
  value: string;
  excluded_reason: string;
}

export interface ConversionRateRecord {
  from_currency: string;
  to_currency: string;
  rate: number;
  provider: string;
  observed_at: string;
}

// ── Trip Handbook (top-level) ───────────────────────────────────────────

export interface TripHandbook {
  trip_title: string;
  traveller_names: string[];
  origin_city: string;
  destinations: string[];
  start_date: string;
  end_date: string;
  total_budget_usd: number;
  travel_style: string;
  group_type: string;
  dietary_restrictions: string[];
  accessibility_needs: string[];

  route_cities: string[];
  route_transport: string[];

  flights: FlightOption[];
  hotels: HotelOption[];
  days: DayPlan[];

  budget_flights: number;
  budget_accommodation: number;
  budget_transport: number;
  budget_meals: number;
  budget_activities: number;
  budget_misc: number;
  budget_total: number;
  budget_per_person: number;
  budget_summary: string;
  budget_base_currency?: string;
  budget_display_currency?: string;
  budget_display_breakdown?: BudgetAmounts | null;
  budget_coverage_status?: "complete" | "complete_with_estimates" | "partial";
  budget_missing_categories?: BudgetCategory[];
  budget_estimated_categories?: BudgetCategory[];
  budget_assumptions?: string[];
  budget_reserve_recommendation?: number;
  budget_display_reserve_recommendation?: number | null;
  budget_contingency_included?: boolean;

  safety: SafetyInfo;
  culture: CultureGuide;
  packing: PackingItem[];
  currency_exchange_locations: CurrencyExchangeLocation[];
  local_tips: LocalTipsApps;
  emergency_info: EmergencyInfo;

  exchange_rate: number;
  local_currency_code: string;
  theme_accent_color: string;
  hero_gradient_from: string;
  hero_gradient_to: string;
  hero_emoji: string;
  season: string;
  generated_at: string;
  langsmith_run_id: string;
}
