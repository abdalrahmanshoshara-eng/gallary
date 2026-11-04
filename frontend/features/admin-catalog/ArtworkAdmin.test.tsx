import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/ar.json";

import type { AdminArtwork } from "./api";
import { ArtworkForm } from "./ArtworkForm";
import { ArtworkStatusPanel } from "./ArtworkStatusPanel";

const replace = vi.fn();
vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace }),
  Link: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function renderUi(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <NextIntlClientProvider locale="ar" messages={messages} timeZone="Asia/Damascus">
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </NextIntlClientProvider>,
  );
}

const ARTWORK = {
  id: "0b7e5d4c-1111-4222-8333-944455556666",
  title: "ياسمين",
  slug: "ياسمين",
  category: 1,
  artist: null,
  creator_name_override: "مجهول",
  materials: [],
  techniques: [],
  tags: [],
  publication_status: "draft",
  published_at: null,
  is_archived: false,
  archived_at: null,
  archive_visibility: "visible",
  images: [],
  publish_problems: ["primary_image_missing"],
  owner_user_phone: null,
  created_at: "2026-11-03T10:00:00Z",
  updated_at: "2026-11-03T10:00:00Z",
} as unknown as AdminArtwork;

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  vi.spyOn(document, "cookie", "get").mockReturnValue("__Host-csrf=tok");
  fetchMock = vi.fn((url: string) => {
    if (url.includes("/admin/catalog/categories"))
      return Promise.resolve(json(200, [{ id: 1, name: "لوحات", parent: null, is_active: true, usage_count: 0 }]));
    if (url.includes("/admin/catalog/")) return Promise.resolve(json(200, []));
    if (url.includes("/admin/artists")) return Promise.resolve(json(200, { count: 0, next: null, previous: null, results: [] }));
    return Promise.resolve(json(500, {}));
  });
  vi.stubGlobal("fetch", fetchMock);
  replace.mockReset();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ArtworkStatusPanel", () => {
  it("explains why a draft cannot be published yet", () => {
    renderUi(<ArtworkStatusPanel artwork={ARTWORK} />);
    expect(screen.getByText("أضف صورة رئيسية للعمل.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "نشر العمل" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "حذف المسودة" })).toBeEnabled();
  });

  it("publishes a ready draft and offers the archive controls afterwards", async () => {
    fetchMock.mockImplementationOnce(() =>
      Promise.resolve(json(200, { ...ARTWORK, publication_status: "published", published_at: "2026-11-03T11:00:00Z", publish_problems: [] })),
    );
    renderUi(<ArtworkStatusPanel artwork={{ ...ARTWORK, publish_problems: [] }} />);
    expect(screen.getByText("العمل جاهز للنشر.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "نشر العمل" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining(`/admin/artworks/${ARTWORK.id}/publish`), expect.anything()));
  });
});

describe("ArtworkForm", () => {
  it("requires a title, a category and a creator before calling the API", async () => {
    renderUi(<ArtworkForm />);
    fireEvent.click(screen.getByRole("button", { name: "إنشاء مسودة" }));
    expect(await screen.findByText("اختر فناناً أو اكتب اسم المُبدع.")).toBeInTheDocument();
    expect(screen.getAllByText("هذا الحقل مطلوب.")).toHaveLength(2);
    expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit | undefined)?.method === "POST")).toBe(false);
  });

  it("creates a draft with empty optional values sent as null and opens the editor", async () => {
    renderUi(<ArtworkForm />);
    await screen.findByRole("option", { name: "لوحات" });
    fireEvent.change(screen.getByLabelText("عنوان العمل"), { target: { value: "ياسمين" } });
    fireEvent.change(screen.getByLabelText("التصنيف"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("اسم المُبدع (إن لم يكن الفنان مسجلاً)"), { target: { value: "مجهول" } });
    fetchMock.mockImplementationOnce(() => Promise.resolve(json(201, ARTWORK)));
    fireEvent.click(screen.getByRole("button", { name: "إنشاء مسودة" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith(`/admin/artworks/${ARTWORK.id}?created=1`));
    const post = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "POST")!;
    const body = JSON.parse(String((post[1] as RequestInit).body));
    expect(body).toMatchObject({ title: "ياسمين", category: 1, artist: null, height_cm: null, year_created: null });
  });
});

describe("ArtworkForm (edit)", () => {
  it("keeps the saved category selected once the options load", async () => {
    renderUi(<ArtworkForm artwork={ARTWORK} />);
    const select = screen.getByLabelText("التصنيف");
    await screen.findByRole("option", { name: "لوحات" });
    expect(select).toHaveValue("1");
  });
});
