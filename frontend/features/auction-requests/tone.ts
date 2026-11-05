import type { Tone } from "@/components/ui/StatusBadge";

const TONES: Record<string, Tone> = {
  submitted: "progress",
  under_review: "progress",
  needs_more_info: "action",
  negotiation: "action",
  approved: "success",
  rejected: "closed",
  withdrawn: "closed",
};

export const requestTone = (status: string): Tone => TONES[status] ?? "progress";
