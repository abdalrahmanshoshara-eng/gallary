import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/ar.json";

import { LoginForm } from "./LoginForm";

const replace = vi.fn();
const refresh = vi.fn();
vi.mock("@/i18n/navigation", () => ({ useRouter: () => ({ replace, refresh }) }));

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function renderForm(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="ar" messages={messages} timeZone="Asia/Damascus">
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

const ME = { id: "u1", phone: "+963944567890", display_name: "", email: null, is_staff: false, roles: [], is_super_admin: false, date_joined: "2026-11-03T10:00:00Z" };
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.spyOn(document, "cookie", "get").mockReturnValue("__Host-csrf=tok");
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  replace.mockReset();
  refresh.mockReset();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("LoginForm", () => {
  it("requests a code, verifies it and redirects to the safe next path", async () => {
    fetchMock
      .mockResolvedValueOnce(json(202, { phone: "+963944567890", expires_in_seconds: 300, resend_after_seconds: 60, channel: "whatsapp" }))
      .mockResolvedValueOnce(json(200, { user: ME, created: true }));
    renderForm(<LoginForm next="/account" />);

    fireEvent.change(screen.getByLabelText("رقم الهاتف"), { target: { value: "٠٩٤٤ ٥٦٧ ٨٩٠" } });
    fireEvent.click(screen.getByRole("button", { name: "أرسل الرمز" }));

    const codeInput = await screen.findByLabelText("رمز التحقق");
    expect(screen.getByText("+963944567890")).toBeInTheDocument();
    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(requestInit.body))).toEqual({ phone: "0944 567 890" });
    expect(new Headers(requestInit.headers).get("X-CSRFToken")).toBe("tok");

    fireEvent.change(codeInput, { target: { value: "482913" } });
    fireEvent.click(screen.getByRole("button", { name: "تأكيد الدخول" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/account"));
    const [url, verifyInit] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/otp/verify");
    expect(JSON.parse(String(verifyInit.body))).toEqual({ phone: "+963944567890", code: "482913" });
  });

  it("validates locally before calling the API", async () => {
    renderForm(<LoginForm next="/account" />);
    fireEvent.change(screen.getByLabelText("رقم الهاتف"), { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "أرسل الرمز" }));
    expect(await screen.findByText("أدخِل رقم هاتف صحيحاً.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the server message with remaining attempts", async () => {
    fetchMock
      .mockResolvedValueOnce(json(202, { phone: "+963944567890", expires_in_seconds: 300, resend_after_seconds: 60, channel: "whatsapp" }))
      .mockResolvedValueOnce(json(400, { error: { code: "OTP_INVALID", message: "الرمز غير صحيح.", details: { remaining_attempts: 2 } } }));
    renderForm(<LoginForm next="/account" />);
    fireEvent.change(screen.getByLabelText("رقم الهاتف"), { target: { value: "0944567890" } });
    fireEvent.click(screen.getByRole("button", { name: "أرسل الرمز" }));
    fireEvent.change(await screen.findByLabelText("رمز التحقق"), { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: "تأكيد الدخول" }));
    expect(await screen.findByText("الرمز غير صحيح. تبقّت محاولتان.")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("explains when login is unavailable (WhatsApp not configured yet)", async () => {
    fetchMock.mockResolvedValueOnce(
      json(503, { error: { code: "OTP_UNAVAILABLE", message: "تسجيل الدخول غير متاح حالياً. يرجى المحاولة لاحقاً.", details: {} } }),
    );
    renderForm(<LoginForm next="/account" />);
    fireEvent.change(screen.getByLabelText("رقم الهاتف"), { target: { value: "0944567890" } });
    fireEvent.click(screen.getByRole("button", { name: "أرسل الرمز" }));
    expect(await screen.findByText("تسجيل الدخول غير متاح حالياً. يرجى المحاولة لاحقاً.")).toBeInTheDocument();
  });
});
