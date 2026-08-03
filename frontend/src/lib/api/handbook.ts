import { apiGet } from "./client";
import type { TripHandbook } from "@/lib/types";

export async function fetchHandbook(sessionId: string): Promise<TripHandbook> {
  return apiGet<TripHandbook>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/handbook`);
}
