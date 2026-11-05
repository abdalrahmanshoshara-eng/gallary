import { useId, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: ReactNode;
  error?: string;
};

/** Labelled input with hint and error wired for screen readers. */
export function Field({ label, hint, error, id, className, ...props }: FieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={inputId} className="text-sm font-medium text-text">
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={[hintId, errorId].filter(Boolean).join(" ") || undefined}
        className={[
          "min-h-11 rounded-[var(--radius-control)] border bg-white px-4 text-base text-text",
          "transition-colors duration-300 ease-calm focus:border-secondary focus:outline-none",
          error ? "border-primary" : "border-border",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
        {...props}
      />
      {hint && !error ? (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-sm text-primary">
          {error}
        </p>
      ) : null}
    </div>
  );
}

type TextAreaFieldProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: string;
  hint?: ReactNode;
  error?: string;
};

/** Multi-line counterpart of Field, same labelling and error wiring. */
export function TextAreaField({ label, hint, error, id, className, rows = 4, ...props }: TextAreaFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={inputId} className="text-sm font-medium text-text">
        {label}
      </label>
      <textarea
        id={inputId}
        rows={rows}
        aria-invalid={error ? true : undefined}
        aria-describedby={[hintId, errorId].filter(Boolean).join(" ") || undefined}
        className={[
          "rounded-[var(--radius-control)] border bg-white px-4 py-3 text-base leading-7 text-text",
          "transition-colors duration-300 ease-calm focus:border-secondary focus:outline-none",
          error ? "border-primary" : "border-border",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
        {...props}
      />
      {hint && !error ? (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-sm text-primary">
          {error}
        </p>
      ) : null}
    </div>
  );
}
