import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/ar.json";

import { AgreementsPanel } from "./AgreementsPanel";
import { sumAmounts } from "./api";
import { SettlementsManager } from "./SettlementsManager";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={String(href)} {...rest}>
      {children}
    </a>
  ),
}));
HTMLDialogElement.prototype.showModal = function () {
  this.setAttribute("open", "");
};
HTMLDialogElement.prototype.close = function () {
  this.removeAttribute("open");
};

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const row = (id: string, payee: string, amount: string, over: Record<string, unknown> = {}) => ({
  id,
  order_number: "ART-2026-000001",
  artwork_title: `عمل ${id}`,
  artwork_id: "aw",
  quantity: 1,
  payee_type: "artist",
  payee_name: payee,
  payee_key: `artist:${payee}`,
  currency: "USD",
  gross_amount: amount,
  commission_rate: "15.00",
  platform_commission: "0.00",
  payee_amount: amount,
  status: "pending",
  status_reason: "",
  paid_at: null,
  reference: "",
  notes: "",
  paid_by: null,
  actions: ["pay", "hold", "cancel"],
  order_cancelled_after_payment: false,
  created_at: "2026-11-08T10:00:00Z",
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
  vi.spyOn(document, "cookie", "get").mockReturnValue("__Host-csrf=tok");
  fetchMock = vi.fn((url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${new URL(url, "http://x").pathname.replace(/^\/api\/v1/, "")}`;
    return Promise.resolve(routes[key] ? routes[key]!(init) : json(404, { error: { code: "NOT_FOUND", message: key } }));
  });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("sumAmounts", () => {
  it("adds decimal strings without float drift", () => {
    expect(sumAmounts(["0.10", "0.20", "1000.05"])).toBe("1000.35");
  });
});

describe("SettlementsManager", () => {
  beforeEach(() => {
    routes = {
      "GET /admin/settlements/summary": () =>
        json(200, { pending: { count: 3, amount: "600.00" }, on_hold: { count: 0, amount: "0.00" }, paid_this_month: { count: 0, amount: "0.00" } }),
      "GET /admin/settlements/payees": () =>
        json(200, [{ payee_key: "artist:فاتح", payee_name: "فاتح", payee_type: "artist", count: 2, amount: "500.00", oldest: "2026-11-08T10:00:00Z" }]),
      "GET /admin/settlements": () =>
        json(200, { count: 3, next: null, previous: null, results: [row("a", "فاتح", "400.00"), row("b", "فاتح", "100.00"), row("c", "ليلى", "100.00")] }),
      "POST /admin/settlements/pay": () => json(200, []),
    };
  });

  it("selects one payee at a time and records a single referenced transfer", async () => {
    renderUi(<SettlementsManager />);
    expect(await screen.findByText("المستحق حسب المستفيد")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("checkbox", { name: "تحديد تسوية عمل a" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "تحديد تسوية عمل b" }));
    expect(screen.getByRole("checkbox", { name: "تحديد تسوية عمل c" })).toBeDisabled();
    expect(screen.getByText(/تسويتان محددة · الصافي/)).toHaveTextContent("500");

    fireEvent.click(screen.getByRole("button", { name: "تسجيل دفع" }));
    const dialog = screen.getByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "تسجيل الدفع" });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("مرجع التحويل (رقم الحوالة أو الإيصال)"), { target: { value: "HW-9" } });
    fireEvent.click(confirm);
    await waitFor(() => expect(screen.getByText("سُجّل الدفع.")).toBeInTheDocument());
    const call = fetchMock.mock.calls.find(([u, i]) => String(u).includes("/settlements/pay") && i?.method === "POST")!;
    const body = JSON.parse(String((call[1] as RequestInit).body));
    expect(body.settlements).toEqual(["a", "b"]);
    expect(body.reference).toBe("HW-9");
    expect(new Headers((call[1] as RequestInit).headers).get("Idempotency-Key")).toBeTruthy();
  });

  it("requires a reason to put a settlement on hold", async () => {
    renderUi(<SettlementsManager />);
    fireEvent.click((await screen.findAllByRole("button", { name: "تعليق" }))[0]!);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("button", { name: "تعليق" })).toBeDisabled();
  });
});

describe("AgreementsPanel", () => {
  const payload = (canManage: boolean) => ({
    active: { id: "g1", commission_rate: "12.00", status: "active", effective_from: "2026-11-01", effective_to: null, notes: "", created_by: "المدير", created_at: "2026-11-01T00:00:00Z" },
    history: [],
    default_commission_rate: "15.00",
    can_manage: canManage,
  });

  it("shows content staff the current rate read-only", async () => {
    routes = { "GET /admin/artists/x/agreements": () => json(200, payload(false)) };
    renderUi(<AgreementsPanel artistId="x" artistName="فاتح" />);
    expect(await screen.findByText(/اتفاقية نشطة: 12%/)).toBeInTheDocument();
    expect(screen.getByText("يحدد المدير العام نسب العمولة.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "اعتماد الاتفاقية" })).toBeNull();
  });

  it("asks the Super Admin to confirm a replacement and its scope", async () => {
    routes = {
      "GET /admin/artists/x/agreements": () => json(200, payload(true)),
      "POST /admin/artists/x/agreements": () => json(201, payload(true)),
    };
    renderUi(<AgreementsPanel artistId="x" artistName="فاتح" />);
    fireEvent.change(await screen.findByLabelText("نسبة المنصة (%)"), { target: { value: "150" } });
    fireEvent.click(screen.getByRole("button", { name: "اعتماد الاتفاقية" }));
    expect(await screen.findByText("أدخل نسبة بين 0 و100.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("نسبة المنصة (%)"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "اعتماد الاتفاقية" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("تنتهي الاتفاقية الحالية (12%) اليوم.")).toBeInTheDocument();
    expect(within(dialog).getByText(/الطلبات القائمة تحتفظ بنسبتها/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "اعتماد الاتفاقية" }));
    expect(await screen.findByText("اعتُمدت الاتفاقية.")).toBeInTheDocument();
  });
});
