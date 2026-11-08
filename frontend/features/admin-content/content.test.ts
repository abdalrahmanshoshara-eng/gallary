import { describe, expect, it, vi } from "vitest";

vi.mock("@/i18n/navigation", () => ({ Link: () => null, usePathname: () => "/" }));

import { validateBanner } from "./BannersManager";

const base = { title: "معرض", link_url: "", link_label: "", starts_at: "", ends_at: "" };

describe("validateBanner", () => {
  it("requires a title and an image", () => {
    expect(validateBanner({ ...base, title: " " }, false)).toEqual({ title: "title", image: "image" });
  });
  it("accepts internal and https links only, with a label", () => {
    expect(validateBanner({ ...base, link_url: "/auctions", link_label: "المزادات" }, true)).toEqual({});
    expect(validateBanner({ ...base, link_url: "javascript:x", link_label: "x" }, true)).toEqual({ link_url: "url" });
    expect(validateBanner({ ...base, link_url: "//evil", link_label: "x" }, true)).toEqual({ link_url: "url" });
    expect(validateBanner({ ...base, link_url: "https://a.b" }, true)).toEqual({ link_label: "label" });
  });
  it("needs the end after the start", () => {
    expect(validateBanner({ ...base, starts_at: "2026-11-10T10:00", ends_at: "2026-11-09T10:00" }, true)).toEqual({ ends_at: "window" });
  });
});
