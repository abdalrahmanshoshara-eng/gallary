import "server-only";

import { notFound } from "next/navigation";

import { ApiError } from "@/lib/api/errors";
import { serverApiGet } from "@/lib/api/server";

/** Fetch an admin resource for a server page; unknown or malformed ids become a 404 page. */
export async function loadAdmin<T>(path: string): Promise<T> {
  try {
    return await serverApiGet<T>(path);
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 400)) notFound();
    throw error;
  }
}

export const isUuid = (value: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
