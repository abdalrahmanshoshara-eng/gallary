"use client";

import { Icon } from "./Icon";

type Props = {
  value: number;
  min?: number;
  max: number;
  onChange: (value: number) => void;
  label: string;
  decreaseLabel: string;
  increaseLabel: string;
  disabled?: boolean;
};

/** − value + with keyboard-accessible buttons; the number itself is announced via aria-live. */
export function QuantityStepper({ value, min = 1, max, onChange, label, decreaseLabel, increaseLabel, disabled }: Props) {
  const button =
    "inline-flex size-10 items-center justify-center text-primary transition-colors duration-300 ease-calm hover:bg-surface disabled:cursor-not-allowed disabled:opacity-40";
  return (
    <div role="group" aria-label={label} className="inline-flex items-center rounded-[var(--radius-control)] border border-border bg-white">
      <button type="button" className={button} aria-label={decreaseLabel} disabled={disabled || value <= min} onClick={() => onChange(value - 1)}>
        <Icon name="minus" className="size-4" />
      </button>
      <span aria-live="polite" className="min-w-10 text-center tabular-nums" dir="ltr">
        {value}
      </span>
      <button type="button" className={button} aria-label={increaseLabel} disabled={disabled || value >= max} onClick={() => onChange(value + 1)}>
        <Icon name="plus" className="size-4" />
      </button>
    </div>
  );
}
