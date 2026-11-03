import type { ReactNode } from "react";

const TONES = {
  error: "border-primary/40 bg-primary/5 text-primary",
  success: "border-olive/40 bg-olive/10 text-olive",
  info: "border-secondary/40 bg-secondary/10 text-text",
} as const;

export function Alert({ tone = "info", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`rounded-[var(--radius-card)] border px-4 py-3 text-sm ${TONES[tone]}`}
    >
      {children}
    </div>
  );
}
