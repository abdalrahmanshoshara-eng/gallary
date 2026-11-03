import { describe, expect, it } from "vitest";

import { safeNextPath } from "./safe-next";

describe("safeNextPath", () => {
  it.each(["/account", "/admin/staff", "/artworks?page=2"])("accepts %s", (path) => {
    expect(safeNextPath(path)).toBe(path);
  });

  it.each([null, "", "account", "//evil.com", "https://evil.com", "/\\evil.com", "/api/v1/auth/me", "/x\nSet-Cookie:a"])(
    "rejects %s",
    (path) => {
      expect(safeNextPath(path)).toBe("/account");
    },
  );
});
