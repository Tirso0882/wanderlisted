// TypeScript enums mirroring src/models/enums.py

export const CabinClass = {
  ECONOMY: "economy",
  PREMIUM_ECONOMY: "premium_economy",
  BUSINESS: "business",
  FIRST: "first",
} as const;
export type CabinClass = (typeof CabinClass)[keyof typeof CabinClass];

export const TransitMode = {
  WALK: "walk",
  TRANSIT: "transit",
  DRIVE: "drive",
  TRAIN: "train",
  BUS: "bus",
  FERRY: "ferry",
  BICYCLE: "bicycle",
  SUBWAY: "subway",
} as const;
export type TransitMode = (typeof TransitMode)[keyof typeof TransitMode];

export const DayPeriod = {
  MORNING: "morning",
  AFTERNOON: "afternoon",
  EVENING: "evening",
} as const;
export type DayPeriod = (typeof DayPeriod)[keyof typeof DayPeriod];

export const AdvisoryLevel = {
  UNKNOWN: "unknown",
  GREEN: "green",
  YELLOW: "yellow",
  ORANGE: "orange",
  RED: "red",
} as const;
export type AdvisoryLevel = (typeof AdvisoryLevel)[keyof typeof AdvisoryLevel];

export const PackingCategory = {
  CLOTHING: "clothing",
  DOCUMENTS: "documents",
  TECH: "tech",
  HEALTH: "health",
  MONEY: "money",
  TOILETRIES: "toiletries",
  ACCESSORIES: "accessories",
} as const;
export type PackingCategory =
  (typeof PackingCategory)[keyof typeof PackingCategory];

export const TravelStyle = {
  BUDGET: "budget",
  MID_RANGE: "mid_range",
  LUXURY: "luxury",
} as const;
export type TravelStyle = (typeof TravelStyle)[keyof typeof TravelStyle];

export const GroupType = {
  SOLO: "solo",
  COUPLE: "couple",
  FAMILY: "family",
  FRIENDS: "friends",
  GROUP: "group",
} as const;
export type GroupType = (typeof GroupType)[keyof typeof GroupType];

export const Season = {
  SPRING: "spring",
  SUMMER: "summer",
  AUTUMN: "autumn",
  WINTER: "winter",
} as const;
export type Season = (typeof Season)[keyof typeof Season];
