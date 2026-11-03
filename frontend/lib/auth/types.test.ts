import { describe, expect, it } from "vitest";

import { hasRole, type CurrentUser } from "./types";

describe("hasRole", () => {
  it("checks role membership and handles anonymous users", () => {
    const user = { roles: ["content_staff"] } as unknown as CurrentUser;
    expect(hasRole(user, "content_staff")).toBe(true);
    expect(hasRole(user, "super_admin")).toBe(false);
    expect(hasRole(null, "content_staff")).toBe(false);
  });
});
