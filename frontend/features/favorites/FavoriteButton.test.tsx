import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ListingsPanel } from "@/features/admin-catalog/ListingsPanel";
import messages from "@/messages/ar.json";

import { FavoriteButton } from "./FavoriteButton";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...rest }: { href: unknown; children: ReactNode }) => (
    <a href={typeof href === "string" ? href : "/login"} {...rest}>
      {children}
    </a>
  ),
}));

const json = (status: number, body: unknown) =>
  new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function renderUi(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="ar" messages={messages} timeZone="Asia/Damascus">
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

const user = (roles: string[]) => ({
  id: "u1",
  phone: "+963944567890",
  display_name: "x",
  first_name: "",
  last_name: "",
  email: null,
  governorate: "",
  city: "",
  address_line: "",
  phone_verified: false,
  is_staff: roles.length > 0,
  roles,
  is_super_admin: roles.includes("super_admin"),
  date_joined: "2026-11-01T00:00:00Z",
});

let routes: Record<string, () => Response>;
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  vi.spyOn(document, "cookie", "get").mockReturnValue("__Host-csrf=tok");
  fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${new URL(url, "http://x").pathname.replace(/^\/api\/v1/, "")}`;
    const handler = routes[key];
    return Promise.resolve(handler ? handler() : json(404, { error: { code: "NOT_FOUND", message: key } }));
  });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("FavoriteButton", () => {
  it("toggles optimistically for a signed-in user", async () => {
    let ids: string[] = [];
    routes = {
      "GET /auth/me": () => json(200, user([])),
      "GET /favorites/ids": () => json(200, { ids }),
      "PUT /favorites/a1": () => {
        ids = ["a1"];
        return json(201, null);
      },
    };
    renderUi(<FavoriteButton artworkId="a1" title="ياسمين" />);
    const button = await screen.findByRole("button", { name: "أضف إلى المفضلة: ياسمين" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    expect(await screen.findByRole("button", { name: "إزالة من المفضلة: ياسمين" })).toHaveAttribute("aria-pressed", "true");
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/favorites/a1"), expect.objectContaining({ method: "PUT" }));
  });

  it("sends visitors to sign in", async () => {
    routes = { "GET /auth/me": () => json(403, { error: { code: "NOT_AUTHENTICATED", message: "x" } }) };
    renderUi(<FavoriteButton artworkId="a1" title="ياسمين" />);
    expect(await screen.findByRole("link", { name: "سجّل الدخول لحفظ الأعمال في المفضلة" })).toBeInTheDocument();
  });
});

describe("ListingsPanel", () => {
  const listing = {
    id: "l1",
    artwork: "a1",
    sale_mode: "fixed_price",
    status: "draft",
    price_usd: null,
    commission_rate_override: null,
    deposit_type: "",
    deposit_value: null,
    pricing_approved_by: null,
    pricing_approved_at: null,
    effective_commission_rate: "15.00",
    effective_deposit: { type: "percentage", value: "30.00", inherited: true },
    quantity_mode: "unique",
    quantity_total: 1,
    quantity_available: 1,
    quantity_reserved: 0,
    quantity_sold: 0,
    max_per_order: 1,
    starts_at: null,
    ends_at: null,
    activated_at: null,
    closed_at: null,
    internal_notes: "",
    activation_problems: ["pricing_not_approved"],
    purchasable: false,
    created_at: "2026-11-04T10:00:00Z",
    updated_at: "2026-11-04T10:00:00Z",
  };

  it("hides pricing from content staff and blocks activation until approved", async () => {
    routes = {
      "GET /auth/me": () => json(200, user(["content_staff"])),
      "GET /admin/artworks/a1/listings": () => json(200, [listing]),
    };
    renderUi(<ListingsPanel artworkId="a1" />);
    expect(await screen.findByText("لم يُعتمد التسعير بعد.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "تفعيل العرض" })).toBeDisabled();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/auth/me"), expect.anything()));
    expect(screen.queryByRole("button", { name: "اعتماد التسعير" })).not.toBeInTheDocument();
  });

  it("lets the Super Admin approve pricing", async () => {
    routes = {
      "GET /auth/me": () => json(200, user(["super_admin"])),
      "GET /admin/artworks/a1/listings": () => json(200, [listing]),
      "POST /admin/listings/l1/pricing": () => json(200, { ...listing, price_usd: "500.00" }),
    };
    renderUi(<ListingsPanel artworkId="a1" />);
    fireEvent.change(await screen.findByLabelText("السعر (USD)"), { target: { value: "500" } });
    fireEvent.click(screen.getByRole("button", { name: "اعتماد التسعير" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/admin/listings/l1/pricing"), expect.anything()),
    );
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/pricing"))!;
    expect(JSON.parse(String((call[1] as RequestInit).body))).toMatchObject({ price_usd: "500", deposit_type: "" });
  });
});
