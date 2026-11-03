"use client";

import { useEffect, useState } from "react";

/** Seconds remaining until `deadline` (ms epoch). Derived during render from a clock tick. */
export function useCountdown(deadline: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!deadline) return;
    const update = () => {
      const tick = Date.now();
      setNow(tick);
      return tick;
    };
    // Refresh the clock right away so a new deadline is never measured against a stale tick.
    const immediate = setTimeout(update, 0);
    const timer = setInterval(() => {
      if (update() >= deadline) clearInterval(timer);
    }, 1000);
    return () => {
      clearTimeout(immediate);
      clearInterval(timer);
    };
  }, [deadline]);
  return deadline ? Math.max(0, Math.ceil((deadline - now) / 1000)) : 0;
}
