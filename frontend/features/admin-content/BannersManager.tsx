"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { cloneElement, useEffect, useId, useMemo, useState, type ReactElement } from "react";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { StatusBadge, type Tone } from "@/components/ui/StatusBadge";
import { fromDamascusInput, toDamascusInput } from "@/lib/formatters/datetime";
import { applyServerErrors, errorText } from "@/lib/forms";

import { bannersKey, createBanner, deleteBanner, listBanners, moveBanner, updateBanner, type AdminBanner } from "./api";
import { MoveButtons } from "./ContentTabs";

const input = "min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3 text-base focus:border-secondary focus:outline-none";
const STATE_TONE: Record<string, Tone> = { live: "success", scheduled: "progress", expired: "closed", hidden: "closed" };
const ACCEPTED = "image/jpeg,image/png,image/webp";

type Errors = Partial<Record<"title" | "image" | "link_url" | "link_label" | "ends_at" | "root", string>>;

export function validateBanner(v: { title: string; link_url: string; link_label: string; starts_at: string; ends_at: string }, hasImage: boolean): Errors {
  const errors: Errors = {};
  if (!v.title.trim()) errors.title = "title";
  if (!hasImage) errors.image = "image";
  const url = v.link_url.trim();
  if (url && !(url.startsWith("https://") || (url.startsWith("/") && !url.startsWith("//")))) errors.link_url = "url";
  if (url && !v.link_label.trim()) errors.link_label = "label";
  if (v.starts_at && v.ends_at && v.ends_at <= v.starts_at) errors.ends_at = "window";
  return errors;
}

/** Label above the control; hint and error below it, announced via aria-describedby (not part of the name). */
function Field({ id, label, hint, error, children }: { id: string; label: string; hint?: string; error?: string; children: ReactElement<Record<string, unknown>> }) {
  const described = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {cloneElement(children, { id, "aria-describedby": described, "aria-invalid": error ? true : undefined })}
      {hint ? (
        <span id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </span>
      ) : null}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-sm text-primary">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function BannerForm({ banner, onDone }: { banner?: AdminBanner; onDone: (rows: AdminBanner[]) => void }) {
  const t = useTranslations("admin.content.banners");
  const [v, setV] = useState({
    title: banner?.title ?? "",
    subtitle: banner?.subtitle ?? "",
    link_url: banner?.link_url ?? "",
    link_label: banner?.link_label ?? "",
    is_active: banner?.is_active ?? true,
    starts_at: banner?.starts_at ? toDamascusInput(banner.starts_at) : "",
    ends_at: banner?.ends_at ? toDamascusInput(banner.ends_at) : "",
  });
  const [file, setFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<Errors>({});
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => void (preview && URL.revokeObjectURL(preview)), [preview]);

  const save = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("title", v.title.trim());
      form.append("subtitle", v.subtitle.trim());
      form.append("link_url", v.link_url.trim());
      form.append("link_label", v.link_label.trim());
      form.append("is_active", v.is_active ? "true" : "false");
      form.append("starts_at", v.starts_at ? fromDamascusInput(v.starts_at)! : "");
      form.append("ends_at", v.ends_at ? fromDamascusInput(v.ends_at)! : "");
      if (file) form.append("image", file);
      return banner ? updateBanner(banner.id, form) : createBanner(form);
    },
    onSuccess: onDone,
    onError: (error) =>
      applyServerErrors(error, (name, err) => setErrors((e) => ({ ...e, [name as string]: err.message })), ["title", "image", "link_url", "link_label", "ends_at"]),
  });
  const uid = useId();
  const msg = (key?: string) =>
    !key ? undefined : key === "title" ? t("errors.title") : key === "image" ? t("errors.image") : key === "url" ? t("errors.url") : key === "label" ? t("errors.label") : key === "window" ? t("errors.window") : key;
  const set = (patch: Partial<typeof v>) => {
    setV((current) => ({ ...current, ...patch }));
    setErrors({});
  };
  const field = (name: keyof Errors) => (errors[name] ? <p role="alert" className="text-sm text-primary">{msg(errors[name])}</p> : null);

  return (
    <form
      noValidate
      className="flex flex-col gap-4 rounded-[var(--radius-card)] border border-secondary/50 bg-white/70 p-5"
      onSubmit={(e) => {
        e.preventDefault();
        const found = validateBanner(v, Boolean(file || banner?.image));
        setErrors(found);
        if (Object.keys(found).length === 0) save.mutate();
      }}
    >
      <h2 className="text-lg font-medium text-primary">{banner ? t("edit") : t("add")}</h2>
      {errors.root ? <Alert tone="error">{errors.root}</Alert> : null}
      <div className="flex flex-col gap-2">
        <span className="text-sm font-medium">{t("image")}</span>
        <div className="aspect-[5/2] overflow-hidden rounded-[var(--radius-control)] bg-surface/60">
          {/* eslint-disable-next-line @next/next/no-img-element -- local preview */}
          {preview ? <img src={preview} alt="" className="size-full object-cover" /> : banner?.image?.variants.length ? <div className="size-full [&_img]:object-cover"><ResponsiveImage image={banner.image} alt="" sizes="40rem" /></div> : null}
        </div>
        <label className="inline-flex w-fit min-h-11 cursor-pointer items-center rounded-[var(--radius-control)] border border-secondary px-4 text-sm text-primary hover:bg-surface">
          {banner?.image || file ? t("replaceImage") : t("image")}
          <input type="file" accept={ACCEPTED} className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <span className="text-xs text-muted">{t("imageHint")}</span>
        {field("image")}
      </div>
      <Field id={`${uid}-title`} label={t("titleField")} error={msg(errors.title)}>
        <input className={input} maxLength={150} value={v.title} onChange={(e) => set({ title: e.target.value })} />
      </Field>
      <Field id={`${uid}-subtitle`} label={t("subtitle")}>
        <input className={input} maxLength={300} value={v.subtitle} onChange={(e) => set({ subtitle: e.target.value })} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id={`${uid}-url`} label={t("linkUrl")} hint={t("linkUrlHint")} error={msg(errors.link_url)}>
          <input className={input} dir="ltr" value={v.link_url} onChange={(e) => set({ link_url: e.target.value })} />
        </Field>
        <Field id={`${uid}-label`} label={t("linkLabel")} error={msg(errors.link_label)}>
          <input className={input} maxLength={60} value={v.link_label} onChange={(e) => set({ link_label: e.target.value })} />
        </Field>
        <Field id={`${uid}-start`} label={t("startsAt")} hint={t("timeHint")}>
          <input type="datetime-local" className={input} dir="ltr" value={v.starts_at} onChange={(e) => set({ starts_at: e.target.value })} />
        </Field>
        <Field id={`${uid}-end`} label={t("endsAt")} error={msg(errors.ends_at)}>
          <input type="datetime-local" className={input} dir="ltr" value={v.ends_at} onChange={(e) => set({ ends_at: e.target.value })} />
        </Field>
      </div>
      <label className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" className="size-4 accent-[var(--color-primary)]" checked={v.is_active} onChange={(e) => set({ is_active: e.target.checked })} />
        {t("active")}
      </label>
      <div className="flex gap-3">
        <Button type="submit" loading={save.isPending}>
          {banner ? t("save") : t("create")}
        </Button>
        <Button variant="ghost" onClick={() => onDone([])} disabled={save.isPending}>
          {t("cancel")}
        </Button>
      </div>
      {save.error && !Object.keys(errors).length ? <Alert tone="error">{errorText(save.error)}</Alert> : null}
    </form>
  );
}

export function BannersManager() {
  const t = useTranslations("admin.content.banners");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [deleting, setDeleting] = useState<AdminBanner | null>(null);
  const banners = useQuery({
    queryKey: bannersKey,
    queryFn: listBanners,
    refetchInterval: (q) => (q.state.data?.some((b) => b.image && b.image.status !== "ready") ? 3000 : false),
  });
  const act = useMutation({
    mutationFn: (fn: () => Promise<AdminBanner[]>) => fn(),
    onSuccess: (rows) => {
      queryClient.setQueryData(bannersKey, rows);
      setDeleting(null);
    },
  });
  const done = (rows: AdminBanner[]) => {
    if (rows.length) queryClient.setQueryData(bannersKey, rows);
    else void banners.refetch();
    setEditing(null);
  };

  if (banners.isPending) return <p className="text-muted">{tc("loading")}</p>;
  if (banners.isError) return <Alert tone="error">{tc("loadError")}</Alert>;
  const rows = banners.data;

  return (
    <div className="flex flex-col gap-6">
      {act.error ? <Alert tone="error">{errorText(act.error)}</Alert> : null}
      {editing === "new" ? <BannerForm onDone={done} /> : <div><Button onClick={() => setEditing("new")}>{t("add")}</Button></div>}
      {rows.length === 0 && editing !== "new" ? <p className="text-muted">{t("empty")}</p> : null}
      <ol className="flex flex-col gap-4">
        {rows.map((banner, index) =>
          editing === banner.id ? (
            <li key={banner.id}>
              <BannerForm banner={banner} onDone={done} />
            </li>
          ) : (
            <li key={banner.id} className="flex flex-col gap-4 rounded-[var(--radius-card)] border border-border/60 p-4 sm:flex-row sm:items-center">
              <div className="aspect-[5/2] w-full shrink-0 overflow-hidden rounded-[var(--radius-control)] bg-surface/60 sm:w-48 [&_img]:object-cover">
                {banner.image?.status === "ready" ? <ResponsiveImage image={banner.image} alt="" sizes="12rem" /> : <span className="flex size-full items-center justify-center text-xs text-muted">{t("processing")}</span>}
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-primary">{banner.title}</p>
                {banner.subtitle ? <p className="text-sm text-muted">{banner.subtitle}</p> : null}
                {banner.link_url ? (
                  <p className="text-xs text-muted">
                    {banner.link_label} · <span dir="ltr">{banner.link_url}</span>
                  </p>
                ) : null}
                <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
                  <StatusBadge tone={STATE_TONE[banner.state] ?? "progress"}>{t(`state.${banner.state}`)}</StatusBadge>
                  <button type="button" className="text-primary underline-offset-4 hover:underline" onClick={() => setEditing(banner.id)}>
                    {tc("edit")}
                  </button>
                  <button type="button" className="text-muted underline-offset-4 hover:text-primary hover:underline" onClick={() => setDeleting(banner)}>
                    {t("delete")}
                  </button>
                </div>
              </div>
              <MoveButtons
                first={index === 0}
                last={index === rows.length - 1}
                busy={act.isPending}
                upLabel={t("up", { title: banner.title })}
                downLabel={t("down", { title: banner.title })}
                onMove={(d) => act.mutate(() => moveBanner(banner.id, d))}
              />
            </li>
          ),
        )}
      </ol>
      <ConfirmDialog
        open={deleting !== null}
        title={deleting ? t("deleteTitle", { title: deleting.title }) : ""}
        confirmLabel={t("confirmDelete")}
        cancelLabel={t("cancel")}
        busy={act.isPending}
        onCancel={() => setDeleting(null)}
        onConfirm={() => deleting && act.mutate(() => deleteBanner(deleting.id))}
      />
    </div>
  );
}
