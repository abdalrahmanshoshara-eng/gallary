import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import { pageCount, parsePage } from "@/lib/catalog/types";

import type { AdminCategory } from "./api";
import { orderCategories } from "./ArtworkForm";
import { applyServerErrors, emptyToNull } from "./form-utils";
import { moveId } from "./ImagesManager";

vi.mock("@/i18n/navigation", () => ({ useRouter: () => ({}), Link: () => null }));

const cat = (id: number, parent: number | null, is_active = true) =>
  ({ id, name: `c${id}`, parent, is_active, usage_count: 0 }) as AdminCategory;

describe("orderCategories", () => {
  it("lists each parent followed by its children and drops inactive ones", () => {
    const rows = orderCategories([cat(3, 1), cat(1, null), cat(2, null), cat(4, 2, false)]);
    expect(rows.map((r) => [r.category.id, r.depth])).toEqual([
      [1, 0],
      [3, 1],
      [2, 0],
    ]);
  });
  it("keeps an inactive category that is already selected", () => {
    expect(orderCategories([cat(2, null), cat(4, 2, false)], 4).map((r) => r.category.id)).toEqual([2, 4]);
  });
});

describe("moveId", () => {
  it("swaps neighbours and ignores moves past the ends", () => {
    expect(moveId(["a", "b", "c"], 2, -1)).toEqual(["a", "c", "b"]);
    expect(moveId(["a", "b", "c"], 0, -1)).toEqual(["a", "b", "c"]);
    expect(moveId(["a", "b", "c"], 2, 1)).toEqual(["a", "b", "c"]);
  });
});

describe("applyServerErrors", () => {
  it("maps known fields and falls back to a root error", () => {
    const setError = vi.fn();
    applyServerErrors(new ApiError(400, "VALIDATION_ERROR", "bad", { title: ["مطلوب"] }), setError, ["title"]);
    expect(setError).toHaveBeenCalledWith("title", { message: "مطلوب" });

    setError.mockReset();
    applyServerErrors(new ApiError(409, "ARTIST_HAS_ARTWORKS", "لا يمكن الحذف"), setError, ["title"]);
    expect(setError).toHaveBeenCalledWith("root", { message: "لا يمكن الحذف" });
  });
  it("converts empty strings to null", () => {
    expect(emptyToNull("")).toBeNull();
    expect(emptyToNull("x")).toBe("x");
  });
});

describe("pagination helpers", () => {
  it("parses only positive integers", () => {
    expect(parsePage("3")).toBe(3);
    expect(parsePage(["2", "9"])).toBe(2);
    expect(parsePage("-1")).toBe(1);
    expect(parsePage("abc")).toBe(1);
    expect(parsePage(undefined)).toBe(1);
    expect(pageCount(0)).toBe(1);
    expect(pageCount(51)).toBe(3);
  });
});
