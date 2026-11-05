const TONES = {
  action: "bg-secondary/15 text-primary ring-secondary/40",
  progress: "bg-surface text-primary ring-border",
  success: "bg-olive/15 text-olive ring-olive/30",
  closed: "bg-text/5 text-muted ring-border",
} as const;

export type Tone = keyof typeof TONES;

const ORDER_TONES: Record<string, Tone> = {
  pending_deposit: "action",
  deposit_confirmed: "progress",
  payment_pending: "progress",
  confirmed: "success",
  completed: "success",
  expired: "closed",
  cancelled_by_customer: "closed",
  cancelled_by_platform: "closed",
};

export const orderTone = (status: string): Tone => ORDER_TONES[status] ?? "progress";

export function StatusBadge({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}>
      {children}
    </span>
  );
}
