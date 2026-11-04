import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/ar.json";

import { LoginForm } from "./LoginForm";
import { RegisterForm } from "./RegisterForm";

const replace = vi.fn();
const refresh = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace, refresh }),
  Link: ({ children }: { children: ReactNode }) => <a>{children}</a>,
}));

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

const ME = {
  id: "u1",
  phone: "+963944567890",
  display_name: "زينة المصري",
  first_name: "زينة",
  last_name: "المصري",
  email: "z@example.com",
  governorate: "damascus",
  city: "المزة",
  address_line: "شارع",
  phone_verified: false,
  is_staff: false,
  roles: [],
  is_super_admin: false,
  date_joined: "2026-11-03T10:00:00Z",
};
let fetchMock: ReturnType<typeof vi.fn>;
const body = (i: number) => JSON.parse(String((fetchMock.mock.calls[i] as [string, RequestInit])[1].body));

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
  it("signs in with phone and password and redirects to the safe next path", async () => {
    fetchMock.mockResolvedValueOnce(json(200, ME));
    renderForm(<LoginForm next="/account" />);
    fireEvent.change(screen.getByLabelText("رقم الهاتف"), { target: { value: "٠٩٤٤ ٥٦٧ ٨٩٠" } });
    fireEvent.change(screen.getByLabelText("كلمة المرور"), { target: { value: "Jasmine2026" } });
    fireEvent.click(screen.getByRole("button", { name: "دخول" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/account"));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/auth/login");
    expect(body(0)).toEqual({ phone: "0944 567 890", password: "Jasmine2026" });
    expect(new Headers(init.headers).get("X-CSRFToken")).toBe("tok");
  });

  it("shows the server's generic error and clears the password", async () => {
    fetchMock.mockResolvedValueOnce(
      json(400, { error: { code: "INVALID_CREDENTIALS", message: "رقم الهاتف أو كلمة المرور غير صحيحة." } }),
    );
    renderForm(<LoginForm next="/" />);
    fireEvent.change(screen.getByLabelText("رقم الهاتف"), { target: { value: "0944567890" } });
    fireEvent.change(screen.getByLabelText("كلمة المرور"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "دخول" }));
    expect(await screen.findByText("رقم الهاتف أو كلمة المرور غير صحيحة.")).toBeInTheDocument();
    expect(screen.getByLabelText("كلمة المرور")).toHaveValue("");
    expect(replace).not.toHaveBeenCalled();
  });

  it("validates before calling the API", async () => {
    renderForm(<LoginForm next="/" />);
    fireEvent.click(screen.getByRole("button", { name: "دخول" }));
    expect(await screen.findByText("أدخِل رقم هاتف صحيحاً.")).toBeInTheDocument();
    expect(screen.getByText("أدخِل كلمة المرور.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("RegisterForm", () => {
  const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

  it("enforces required fields and password rules on the client", async () => {
    renderForm(<RegisterForm next="/" />);
    fill("كلمة المرور", "abcdefgh");
    fill("تأكيد كلمة المرور", "different1");
    fireEvent.click(screen.getByRole("button", { name: "إنشاء الحساب" }));
    expect(await screen.findByText("كلمة المرور يجب أن تحتوي على حرف ورقم على الأقل.")).toBeInTheDocument();
    expect(screen.getByText("كلمتا المرور غير متطابقتين.")).toBeInTheDocument();
    expect(screen.getAllByText("هذا الحقل مطلوب.").length).toBeGreaterThanOrEqual(5);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("registers, signs in and maps server field errors", async () => {
    fetchMock
      .mockResolvedValueOnce(
        json(400, {
          error: {
            code: "VALIDATION_ERROR",
            message: "تحقق من البيانات.",
            details: { password: ["كلمة المرور هذه شائعة جداً."] },
          },
        }),
      )
      .mockResolvedValueOnce(json(201, ME));
    renderForm(<RegisterForm next="/artworks" />);
    fill("الاسم الأول", "زينة");
    fill("الكنية", "المصري");
    fill("رقم الهاتف", "0944567890");
    fill("البريد الإلكتروني", "z@example.com");
    fill("المحافظة", "damascus");
    fill("المدينة / المنطقة", "المزة");
    fill("العنوان التفصيلي", "شارع الجلاء");
    fill("كلمة المرور", "password1");
    fill("تأكيد كلمة المرور", "password1");
    fireEvent.click(screen.getByRole("button", { name: "إنشاء الحساب" }));
    expect(await screen.findByText("كلمة المرور هذه شائعة جداً.")).toBeInTheDocument();

    fill("كلمة المرور", "Jasmine2026");
    fill("تأكيد كلمة المرور", "Jasmine2026");
    fireEvent.click(screen.getByRole("button", { name: "إنشاء الحساب" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/artworks"));
    expect(body(1)).toMatchObject({ phone: "0944567890", governorate: "damascus", password_confirm: "Jasmine2026" });
  });
});
