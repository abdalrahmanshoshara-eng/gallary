import type { components } from "@/types/api";

/** Shorthand for schemas generated from the backend OpenAPI document. */
export type Schema<Name extends keyof components["schemas"]> = components["schemas"][Name];
