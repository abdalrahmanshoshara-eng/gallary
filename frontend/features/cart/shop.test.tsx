import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CheckoutForm } from "@/features/orders/CheckoutForm";
import { OrderView } from "@/features/orders/OrderView";
import type { CurrentUser } from "@/lib/auth/types";
import messages from "@/messages/ar.json";

import { BuyBox } from "./BuyBox";
import { CartView } from "./CartView";

const replace = vi.fn();
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useSearchParams: () => search }));
vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...rest }: { href: unknown; children: ReactNode }) => (
    <a
      href={
        typeof href === "string"
          ? href
          : `${(href as { pathname: string }).pathname}?${new URLSearchParams((href as { query?: Record<string, string> }).query)}`
      }
      {...rest}
    >
      {children}
    </a>
  ),
  useRouter: () => ({ replace, refresh: vi.fn() }),
  usePathname: () => "/artworks/jasmine",
}));
HTMLDialogElement.prototype.showModal = function () {
  this.setAttribute("open", "");
};
HTMLDialogElement.prototype.close = function () {
  this.removeAttribute("open");
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const me = (staff = false): CurrentUser => ({
  id: "u1",
  phone: "+963944567890",
  display_name: "زينة",
  first_name: "زينة",
  last_name: "م",
  email: "z@example.com",
  governorate: "damascus",
  city: "المزة",
  address_line: "شارع",
  phone_verified: false,
  is_staff: staff,
  roles: staff ? ["content_staff"] : [],
  is_super_admin: false,
  date_joined: "2026-11-01T00:00:00Z",
}) as CurrentUser;
const OFFER = {
  id: "off-1",
  sale_mode: "fixed_price",
  status: "active",
  price_usd: "750.00",
  quantity_mode: "limited",
  available: 3,
  max_per_order: 2,
  starts_at: null,
  ends_at: null,
  purchasable: true,
  unavailable_reason: null,
  auction_id: null,
};
const line = (over: Record<string, unknown> = {}) => ({
  id: "line-1",
  listing: "off-1",
  artwork_slug: "jasmine",
  title: "ياسمين الشام",
  creator_name: "فاتح",
  image: null,
  quantity: 1,
  max_quantity: 2,
  quantity_mode: "limited",
  unit_price: "750.00",
  price_at_add: "750.00",
  price_changed: false,
  line_total: "750.00",
  deposit: "225.00",
  problem: null,
  ...over,
});
const cart = (lines: unknown[], over: Record<string, unknown> = {}) => ({
  lines,
  count: lines.length,
  subtotal: "750.00",
  deposit_due: "225.00",
  remaining_after_deposit: "525.00",
  can_checkout: true,
  blocking: [],
  max_items: 20,
  ...over,
});

let routes: Record<string, (init?: RequestInit) => Response>;
let fetchMock: ReturnType<typeof vi.fn>;
function renderUi(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="ar" messages={messages} timeZone="Asia/Damascus">
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
}
beforeEach(() => {
  search = new URLSearchParams();
  replace.mockReset();
  vi.spyOn(document, "cookie", "get").mockReturnValue("__Host-csrf=tok");
  fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${new URL(url, "http://x").pathname.replace(/^\/api\/v1/, "")}`;
    const handler = routes[key];
    return Promise.resolve(handler ? handler(init) : json(404, { error: { code: "NOT_FOUND", message: key } }));
  });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
const calls = (method: string, path: string) =>
  fetchMock.mock.calls.filter(([u, i]) => (i?.method ?? "GET") === method && String(u).includes(path));

describe("BuyBox", () => {
  it("sends visitors to sign in and keeps the chosen quantity", async () => {
    routes = { "GET /auth/me": () => json(403, { error: { code: "NOT_AUTHENTICATED", message: "x" } }) };
    renderUi(<BuyBox offer={OFFER} />);
    fireEvent.click(await screen.findByRole("button", { name: "زيادة الكمية" }));
    const link = screen.getByRole("link", { name: "سجّل الدخول للشراء" });
    expect(decodeURIComponent(link.getAttribute("href")!)).toContain("next=/artworks/jasmine?add=off-1&qty=2");
  });

  it("shows staff a note instead of a buy button", async () => {
    routes = { "GET /auth/me": () => json(200, me(true)) };
    renderUi(<BuyBox offer={OFFER} />);
    expect(await screen.findByText("الشراء متاح لحسابات العملاء فقط.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /أضف إلى العربة/ })).not.toBeInTheDocument();
  });

  it("adds for a customer and then offers checkout", async () => {
    let current = cart([]);
    routes = {
      "GET /auth/me": () => json(200, me()),
      "GET /cart": () => json(200, current),
      "POST /cart/items": () => {
        current = cart([line({ quantity: 2 })]);
        return json(201, current);
      },
    };
    renderUi(<BuyBox offer={OFFER} />);
    fireEvent.click(await screen.findByRole("button", { name: "زيادة الكمية" }));
    fireEvent.click(screen.getByRole("button", { name: /أضف إلى العربة/ }));
    expect(await screen.findByRole("link", { name: "إتمام الطلب" })).toHaveAttribute("href", "/checkout");
    expect(JSON.parse(String(calls("POST", "/cart/items")[0]![1]!.body))).toEqual({ listing: "off-1", quantity: 2 });
  });

  it("completes the add-to-cart intent after sign-in exactly once", async () => {
    search = new URLSearchParams("add=off-1&qty=2");
    let current = cart([]);
    routes = {
      "GET /auth/me": () => json(200, me()),
      "GET /cart": () => json(200, current),
      "POST /cart/items": () => {
        current = cart([line({ quantity: 2 })]);
        return json(201, current);
      },
    };
    renderUi(<BuyBox offer={OFFER} />);
    expect(await screen.findByText("أهلاً بعودتك — أُضيفت القطعة إلى عربتك.")).toBeInTheDocument();
    expect(calls("POST", "/cart/items")).toHaveLength(1);
    expect(replace).toHaveBeenCalledWith("/artworks/jasmine", { scroll: false });
  });
});

describe("CartView", () => {
  it("shows the empty state", async () => {
    routes = { "GET /auth/me": () => json(200, me()), "GET /cart": () => json(200, cart([], { blocking: ["empty"], can_checkout: false })) };
    renderUi(<CartView />);
    expect(await screen.findByText("عربتك فارغة.")).toBeInTheDocument();
  });

  it("blocks checkout until changed prices are accepted", async () => {
    let current = cart([line({ price_changed: true, price_at_add: "700.00" })], { blocking: ["price_changed"], can_checkout: false });
    routes = {
      "GET /auth/me": () => json(200, me()),
      "GET /cart": () => json(200, current),
      "POST /cart/accept-prices": () => {
        current = cart([line()]);
        return json(200, current);
      },
    };
    renderUi(<CartView />);
    expect(await screen.findByText(/تغيّر السعر من/)).toBeInTheDocument();
    for (const button of screen.getAllByRole("button", { name: "متابعة لتأكيد الطلب" })) expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "اعتماد الأسعار الجديدة" }));
    await waitFor(() => expect(screen.getAllByRole("link", { name: "متابعة لتأكيد الطلب" })[0]).toHaveAttribute("href", "/checkout"));
  });

  it("explains unavailable lines", async () => {
    routes = {
      "GET /auth/me": () => json(200, me()),
      "GET /cart": () => json(200, cart([line({ problem: "reserved" })], { blocking: ["unavailable"], can_checkout: false })),
    };
    renderUi(<CartView />);
    expect(await screen.findByText("محجوزة حالياً لعميل آخر.")).toBeInTheDocument();
    expect(screen.getByText("بعض العناصر لم تعد متاحة. احذفها للمتابعة.")).toBeInTheDocument();
  });
});

describe("CheckoutForm", () => {
  const POLICY = { version: "2026-11-05", title: "سياسة العربون والإلغاء", points: ["تأكيد الطلب يحجز القطع لك لمدة 24 ساعة."], reservation_hours: 24 };

  it("requires the policy, sends one idempotency key and opens the order", async () => {
    routes = {
      "GET /auth/me": () => json(200, me()),
      "GET /cart": () => json(200, cart([line()])),
      "GET /orders/policy": () => json(200, POLICY),
      "POST /orders/checkout": () => json(201, { number: "ART-2026-000001" }),
    };
    renderUi(<CheckoutForm user={me()} />);
    const submit = await screen.findByRole("button", { name: "تأكيد الطلب وحجز القطع" });
    expect(screen.getByLabelText("المدينة / المنطقة")).toHaveValue("المزة"); // prefilled from the profile
    fireEvent.click(submit);
    expect(await screen.findByText("يجب الموافقة على السياسة لإتمام الطلب.")).toBeInTheDocument();
    expect(calls("POST", "/orders/checkout")).toHaveLength(0);

    fireEvent.click(screen.getByLabelText("قرأت سياسة العربون والإلغاء وأوافق عليها."));
    fireEvent.click(submit);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/orders/ART-2026-000001?created=1"));
    const [, init] = calls("POST", "/orders/checkout")[0]!;
    expect(new Headers(init!.headers).get("Idempotency-Key")).toMatch(/.{8,}/);
    expect(JSON.parse(String(init!.body))).toMatchObject({ policy_version: "2026-11-05", accept_policy: true, governorate: "damascus" });
  });

  it("sends the customer back to the cart when prices changed meanwhile", async () => {
    routes = {
      "GET /auth/me": () => json(200, me()),
      "GET /cart": () => json(200, cart([line()])),
      "GET /orders/policy": () => json(200, POLICY),
      "POST /orders/checkout": () => json(409, { error: { code: "PRICE_CHANGED", message: "تغيّرت أسعار بعض العناصر." } }),
    };
    renderUi(<CheckoutForm user={me()} />);
    fireEvent.click(await screen.findByLabelText("قرأت سياسة العربون والإلغاء وأوافق عليها."));
    fireEvent.click(screen.getByRole("button", { name: "تأكيد الطلب وحجز القطع" }));
    const alert = await screen.findByText(/تغيّرت أسعار بعض العناصر\./);
    expect(within(alert).getByRole("link", { name: "مراجعة العربة" })).toHaveAttribute("href", "/cart");
  });
});

describe("OrderView", () => {
  const ORDER = {
    number: "ART-2026-000001",
    status: "pending_deposit",
    subtotal: "750.00",
    deposit_due: "225.00",
    amount_paid: "0.00",
    remaining: "750.00",
    item_count: 1,
    reservation_expires_at: "2026-11-06T10:00:00Z",
    server_now: "2026-11-05T12:00:00Z",
    needs_action: true,
    created_at: "2026-11-05T10:00:00Z",
    deposit_status: "pending",
    payment_status: "unpaid",
    can_cancel: true,
    whatsapp_url: "https://wa.me/963944000111?text=x",
    contact_name: "زينة",
    contact_phone: "+963944567890",
    contact_email: "",
    governorate: "damascus",
    city: "المزة",
    address_line: "شارع",
    customer_notes: "",
    cancelled_reason: "",
    items: [{ id: "i1", artwork_slug: "jasmine", title: "ياسمين الشام", image: null, quantity: 1, unit_price: "750.00", line_total: "750.00", status: "active" }],
    history: [],
    delivery: { status: "not_started", method: "", delivered_at: null },
  };

  it("leads with the deadline and the WhatsApp action, and cancels via a dialog", async () => {
    let current: Record<string, unknown> = ORDER;
    routes = {
      "GET /orders/ART-2026-000001": () => json(200, current),
      "POST /orders/ART-2026-000001/cancel": () => {
        current = { ...ORDER, status: "cancelled_by_customer", can_cancel: false, whatsapp_url: null };
        return json(200, current);
      },
    };
    renderUi(<OrderView number="ART-2026-000001" justCreated />);
    expect(await screen.findByText("تم تأكيد طلبك وحجز القطع لك.")).toBeInTheDocument();
    expect(screen.getByRole("timer")).toHaveTextContent("22 س");
    const whatsapp = screen.getByRole("link", { name: "تواصل عبر WhatsApp لدفع العربون" });
    expect(whatsapp).toHaveAttribute("target", "_blank");
    expect(screen.queryByText(/تم الإرسال/)).not.toBeInTheDocument(); // BR-312

    fireEvent.click(screen.getByRole("button", { name: "إلغاء الطلب" }));
    fireEvent.click(await screen.findByRole("button", { name: "نعم، ألغِ الطلب" }));
    expect(await screen.findByText("أُلغي الطلب.")).toBeInTheDocument();
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
  });
});
