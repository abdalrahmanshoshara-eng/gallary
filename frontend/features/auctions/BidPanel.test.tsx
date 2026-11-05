import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { pickImages } from "@/features/auction-requests/RequestForm";
import type { CurrentUser } from "@/lib/auth/types";
import messages from "@/messages/ar.json";

import type { AuctionDetail } from "./api";
import { BidPanel } from "./BidPanel";
import type { AuctionState } from "./live";

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
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/auctions/a1",
}));
HTMLDialogElement.prototype.showModal = function () {
  this.setAttribute("open", "");
};
HTMLDialogElement.prototype.close = function () {
  this.removeAttribute("open");
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const user = (staff = false) =>
  ({ id: "u1", phone: "+963944567890", display_name: "زينة", is_staff: staff, roles: staff ? ["auction_manager"] : [], is_super_admin: false }) as unknown as CurrentUser;

const DETAIL = {
  id: "a1",
  minimum_increment: "10.00",
  winner_deposit_percent: "50.00",
  winner_payment_window_sec: 3600,
} as AuctionDetail;
const STATE: AuctionState = {
  seq: 4,
  server_time: "2026-11-05T10:00:00Z",
  status: "live",
  outcome: "",
  current_price: "100.00",
  minimum_next_bid: "110.00",
  bid_count: 1,
  starts_at: "2026-11-05T09:00:00Z",
  ends_at: "2026-11-05T12:00:00Z",
  extensions_count: 0,
  reserve_met: null,
  payment_deadline: null,
  winner_alias: null,
  bids: [],
  me: { alias: 2, my_top_bid: "90.00", is_highest: false, is_winner: false, order_number: null, can_bid: true },
} as unknown as AuctionState;

let routes: Record<string, (init?: RequestInit) => Response | Promise<Response>>;
let fetchMock: ReturnType<typeof vi.fn>;
const onAccepted = vi.fn();
const onStale = vi.fn();

function renderPanel(state: AuctionState = STATE, phase: "live" | "upcoming" | "closing" = "live") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="ar" messages={messages} timeZone="Asia/Damascus">
      <QueryClientProvider client={client}>
        <BidPanel detail={DETAIL} state={state} phase={phase} onAccepted={onAccepted} onStale={onStale} />
      </QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

beforeEach(() => {
  onAccepted.mockReset();
  onStale.mockReset();
  vi.spyOn(document, "cookie", "get").mockReturnValue("__Host-csrf=tok");
  routes = { "GET /auth/me": () => json(200, user()) };
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
const bidCalls = () => fetchMock.mock.calls.filter(([u, i]) => i?.method === "POST" && String(u).includes("/bids"));
const keyOf = (call: unknown[]) => new Headers((call[1] as RequestInit).headers).get("Idempotency-Key");

describe("BidPanel", () => {
  it("sends visitors to sign in and back to the auction", async () => {
    routes["GET /auth/me"] = () => json(403, { error: { code: "NOT_AUTHENTICATED", message: "x" } });
    renderPanel();
    const link = await screen.findByRole("link", { name: "سجّل الدخول للمزايدة" });
    expect(decodeURIComponent(link.getAttribute("href")!)).toContain("next=/auctions/a1");
  });

  it("lets staff follow without a bid field", async () => {
    routes["GET /auth/me"] = () => json(200, user(true));
    renderPanel();
    expect(await screen.findByText(/المزايدة متاحة لحسابات العملاء فقط/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "زايد" })).toBeNull();
  });

  it("disables bidding for the current highest bidder (BR-508)", async () => {
    renderPanel({ ...STATE, me: { ...STATE.me!, is_highest: true, my_top_bid: "100.00" } });
    expect(await screen.findByText("أنت المزايد الأعلى حالياً")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("tells an outbid bidder and prefills the minimum", async () => {
    renderPanel();
    expect(await screen.findByText("تم تجاوز مزايدتك")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "مبلغ مزايدتك (USD)" })).toHaveValue("110.00");
  });

  it("checks the minimum locally, then confirms and sends one idempotent bid", async () => {
    routes["POST /auctions/a1/bids"] = () =>
      json(201, { bid: { id: "b9", amount: "150.00", alias: 2, created_at: STATE.ends_at }, state: { ...STATE, seq: 5 }, replayed: false });
    renderPanel();
    const input = await screen.findByRole("textbox", { name: "مبلغ مزايدتك (USD)" });
    fireEvent.change(input, { target: { value: "105" } });
    fireEvent.click(screen.getByRole("button", { name: "زايد" }));
    expect(await screen.findByText(/المزايدة يجب ألا تقل عن/)).toBeInTheDocument();
    expect(bidCalls()).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /150/ }));
    fireEvent.click(screen.getByRole("button", { name: "زايد" }));
    expect(await screen.findByText(/تأكيد مزايدة بمبلغ/)).toBeInTheDocument();
    expect(screen.getByText(/المزايدة ملزمة ولا يمكن سحبها/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "نعم، زايد" }));
    await waitFor(() => expect(onAccepted).toHaveBeenCalled());
    expect(bidCalls()).toHaveLength(1);
    expect(JSON.parse(String((bidCalls()[0]![1] as RequestInit).body))).toEqual({ amount: "150.00" });
    expect(keyOf(bidCalls()[0]!)).toBeTruthy();
  });

  it("explains a lost race in plain language and moves the field to the new minimum", async () => {
    routes["POST /auctions/a1/bids"] = () =>
      json(409, {
        error: { code: "BID_REJECTED", message: "x", details: { reason: "too_low", minimum_next_bid: "160.00", current_price: "150.00" } },
      });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "زايد" }));
    fireEvent.click(await screen.findByRole("button", { name: "نعم، زايد" }));
    expect(await screen.findByText(/سبقك مزايد آخر — الحد الأدنى الآن/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "مبلغ مزايدتك (USD)" })).toHaveValue("160.00");
    expect(onStale).toHaveBeenCalled();
  });

  it("retries an unconfirmed bid with the same key after a network failure", async () => {
    let attempts = 0;
    routes["POST /auctions/a1/bids"] = () => {
      attempts += 1;
      if (attempts === 1) throw new TypeError("network");
      return json(200, { bid: { id: "b9", amount: "110.00", alias: 2, created_at: STATE.ends_at }, state: STATE, replayed: true });
    };
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const key = `${init?.method ?? "GET"} ${new URL(url, "http://x").pathname.replace(/^\/api\/v1/, "")}`;
      try {
        return Promise.resolve(routes[key] ? routes[key]!(init) : json(404, {}));
      } catch (error) {
        return Promise.reject(error);
      }
    });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "زايد" }));
    fireEvent.click(await screen.findByRole("button", { name: "نعم، زايد" }));
    fireEvent.click(await screen.findByRole("button", { name: "أعد إرسال المزايدة نفسها" }));
    await waitFor(() => expect(onAccepted).toHaveBeenCalled());
    expect(bidCalls()).toHaveLength(2);
    expect(keyOf(bidCalls()[0]!)).toBe(keyOf(bidCalls()[1]!));
  });

  it("shows the closing state while the server resolves the end", async () => {
    renderPanel(STATE, "closing");
    expect(await screen.findByText(/جارٍ إغلاق المزاد/)).toBeInTheDocument();
  });
});

describe("pickImages", () => {
  const file = (name: string, type: string, size = 10) => new File([new Uint8Array(size)], name, { type });
  it("keeps supported images within the room left and names rejections", () => {
    const result = pickImages([file("a.jpg", "image/jpeg"), file("b.gif", "image/gif"), file("c.png", "image/png")], 1);
    expect(result.accepted.map((f) => f.name)).toEqual(["a.jpg"]);
    expect(result.rejected).toEqual(["b.gif"]);
    expect(result.overflow).toBe(true);
  });
});
