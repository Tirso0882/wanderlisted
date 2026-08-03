import { apiPost } from "./client";
import type { ResumeResponse, ResumeRequest } from "@/lib/types";

/**
 * Resume a HITL-interrupted session with the user's decision.
 */
export async function resumeChat(request: ResumeRequest): Promise<ResumeResponse> {
  return apiPost<ResumeResponse>("/api/v1/chat/resume", request);
}
