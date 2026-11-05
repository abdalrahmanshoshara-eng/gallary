"use client";

import { useEffect, useState } from "react";

/**
 * Time left until `deadline`, corrected by the server clock (`serverNow`) so a wrong device
 * clock never shows a wrong deadline. Calls `onElapsed` once when it reaches zero.
 */
export function useCountdown(deadline: string, serverNow: string, onElapsed?: () => void): number {
  const [offset] = useState(() => Date.parse(serverNow) - Date.now());
  const remaining = () => Math.max(0, Date.parse(deadline) - (Date.now() + offset));
  const [left, setLeft] = useState(remaining);
  useEffect(() => {
    const timer = setInterval(() => {
      const value = remaining();
      setLeft(value);
      if (value === 0) {
        clearInterval(timer);
        onElapsed?.();
      }
    }, 1000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the deadline identity is the dependency
  }, [deadline]);
  return left;
}

export function splitDuration(ms: number) {
  const total = Math.floor(ms / 1000);
  return { hours: Math.floor(total / 3600), minutes: Math.floor((total % 3600) / 60), seconds: total % 60 };
}
