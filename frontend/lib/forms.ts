import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { ApiError } from "@/lib/api/errors";

/** Map a backend VALIDATION_ERROR onto form fields; anything else becomes a root error. */
export function applyServerErrors<T extends FieldValues>(error: unknown, setError: UseFormSetError<T>, fields: string[]) {
  if (!(error instanceof ApiError)) return;
  const fieldErrors = error.fieldErrors;
  let mapped = false;
  for (const [field, messages] of Object.entries(fieldErrors)) {
    if (fields.includes(field) && messages[0]) {
      setError(field as Path<T>, { message: messages[0] });
      mapped = true;
    }
  }
  if (!mapped) setError("root" as Path<T>, { message: error.message });
}

/** "" → null for optional numbers/relations sent to the API. */
export const emptyToNull = (value: string | null | undefined) => (value === undefined || value === "" ? null : value);

/** Human-readable message for any thrown value (ApiError messages are already localised). */
export const errorText = (error: unknown) =>
  error instanceof ApiError ? error.message : error instanceof Error ? error.message : String(error);
