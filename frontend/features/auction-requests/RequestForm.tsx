"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, TextAreaField } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { useRouter } from "@/i18n/navigation";
import { applyServerErrors } from "@/lib/forms";

import { requestKey, requestsKey, submitRequest, updateRequest, type AuctionRequest, type RequestFields } from "./api";

export const MAX_IMAGES = 10;
const MAX_MB = 15;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const FIELDS: (keyof RequestFields)[] = [
  "work_title",
  "work_description",
  "artist_name",
  "artist_info",
  "category_hint",
  "dimensions_text",
  "year_text",
  "expected_price",
  "customer_notes",
];

const schema = z.object({
  work_title: z.string().trim().min(1, "required").max(250),
  work_description: z.string().trim().min(1, "required").max(5000),
  artist_name: z.string().trim().min(1, "required").max(200),
  artist_info: z.string().trim().max(3000),
  category_hint: z.string().trim().max(120),
  dimensions_text: z.string().trim().max(120),
  year_text: z.string().trim().max(40),
  expected_price: z
    .string()
    .trim()
    .refine((v) => v === "" || (/^\d{1,10}(\.\d{1,2})?$/.test(v) && Number(v) >= 1), "price"),
  customer_notes: z.string().trim().max(3000),
});
type Values = z.infer<typeof schema>;

/** Validates picked files before upload; returns accepted files and readable rejections. */
export function pickImages(files: File[], room: number): { accepted: File[]; rejected: string[]; overflow: boolean } {
  const valid: File[] = [];
  const rejected: string[] = [];
  for (const file of files) {
    if (!ACCEPTED.includes(file.type) || file.size > MAX_MB * 1024 * 1024) rejected.push(file.name);
    else valid.push(file);
  }
  return { accepted: valid.slice(0, Math.max(0, room)), rejected, overflow: valid.length > room };
}

function Previews({ files, onRemove }: { files: File[]; onRemove: (index: number) => void }) {
  const t = useTranslations("auctionRequests.fields");
  const urls = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);
  useEffect(() => () => urls.forEach((url) => URL.revokeObjectURL(url)), [urls]);
  if (files.length === 0) return null;
  return (
    <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5">
      {urls.map((url, index) => (
        <li key={url} className="relative aspect-square overflow-hidden rounded-[var(--radius-control)] bg-surface/60">
          {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview */}
          <img src={url} alt="" className="size-full object-cover" />
          <button
            type="button"
            onClick={() => onRemove(index)}
            aria-label={t("removeImage", { index: index + 1 })}
            className="absolute end-1 top-1 inline-flex size-8 items-center justify-center rounded-full bg-white/90 text-primary shadow hover:bg-white"
          >
            <Icon name="close" className="size-4" />
          </button>
        </li>
      ))}
    </ul>
  );
}

/**
 * Submit a new auction request, or edit one the team sent back for more information.
 * Only the work's facts are asked; contact details come from the account.
 */
export function RequestForm({ existing, onDone }: { existing?: AuctionRequest; onDone?: () => void }) {
  const t = useTranslations("auctionRequests");
  const router = useRouter();
  const queryClient = useQueryClient();
  const picker = useRef<HTMLInputElement>(null);
  const [images, setImages] = useState<File[]>([]);
  const [imageError, setImageError] = useState<string | null>(null);
  const already = existing?.images.length ?? 0;
  const room = MAX_IMAGES - already - images.length;

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      work_title: existing?.work_title ?? "",
      work_description: existing?.work_description ?? "",
      artist_name: existing?.artist_name ?? "",
      artist_info: existing?.artist_info ?? "",
      category_hint: existing?.category_hint ?? "",
      dimensions_text: existing?.dimensions_text ?? "",
      year_text: existing?.year_text ?? "",
      expected_price: existing?.expected_price ? String(Number(existing.expected_price)) : "",
      customer_notes: existing?.customer_notes ?? "",
    },
  });

  const save = useMutation({
    mutationFn: (values: Values) =>
      existing ? updateRequest({ id: existing.id, fields: values, images }) : submitRequest({ fields: values, images }),
    onSuccess: (request) => {
      queryClient.setQueryData(requestKey(request.id), request);
      void queryClient.invalidateQueries({ queryKey: requestsKey });
      if (existing) onDone?.();
      else router.push(`/auction-requests/${request.id}?submitted=1`);
    },
    onError: (error) => applyServerErrors(error, form.setError, [...FIELDS]),
  });

  const e = form.formState.errors;
  const msg = (m?: string) => (m === "required" ? t("errors.required") : m === "price" ? t("errors.price") : m);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const { accepted, rejected, overflow } = pickImages(Array.from(list), room);
    setImages((current) => [...current, ...accepted]);
    setImageError(
      rejected.length
        ? t("errors.badImage", { name: rejected[0]!, mb: MAX_MB })
        : overflow
          ? t("errors.tooManyImages", { max: MAX_IMAGES })
          : null,
    );
    if (picker.current) picker.current.value = "";
  };

  return (
    <form noValidate onSubmit={form.handleSubmit((values) => save.mutate(values))} className="flex flex-col gap-10">
      {e.root ? <Alert tone="error">{e.root.message}</Alert> : null}

      <fieldset className="grid gap-6">
        <legend className="mb-4 text-lg font-medium text-primary">{t("details")}</legend>
        <Field label={t("fields.work_title")} required error={msg(e.work_title?.message)} {...form.register("work_title")} />
        <TextAreaField
          label={t("fields.work_description")}
          hint={t("fields.work_descriptionHint")}
          required
          rows={5}
          error={msg(e.work_description?.message)}
          {...form.register("work_description")}
        />
        <Field label={t("fields.artist_name")} required error={msg(e.artist_name?.message)} {...form.register("artist_name")} />
      </fieldset>

      <fieldset className="grid gap-4">
        <legend className="mb-2 text-lg font-medium text-primary">{t("fields.images")}</legend>
        <p className="text-sm text-muted">{t("fields.imagesHint", { max: MAX_IMAGES })}</p>
        {existing && already ? (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-muted">{t("existingImages")}</p>
            <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5">
              {existing.images.map((image) => (
                <li key={image.id} className="aspect-square overflow-hidden rounded-[var(--radius-control)] bg-surface/60 p-1">
                  {image.variants.length ? <ResponsiveImage image={image} alt="" sizes="8rem" /> : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <Previews files={images} onRemove={(index) => setImages((current) => current.filter((_, i) => i !== index))} />
        {imageError ? (
          <p role="alert" className="text-sm text-primary">
            {imageError}
          </p>
        ) : null}
        <div className="flex flex-wrap items-center gap-4">
          <input
            ref={picker}
            type="file"
            accept={ACCEPTED.join(",")}
            multiple
            className="sr-only"
            id="request-images"
            onChange={(event) => addFiles(event.target.files)}
            disabled={room <= 0}
          />
          <label
            htmlFor="request-images"
            aria-disabled={room <= 0}
            className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-[var(--radius-control)] border border-secondary px-5 text-sm font-medium text-primary hover:bg-surface aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
          >
            <Icon name="plus" className="size-4" />
            {t("fields.addImages")}
          </label>
          <span className="text-xs text-muted tabular-nums">{t("fields.imagesCount", { count: already + images.length, max: MAX_IMAGES })}</span>
        </div>
      </fieldset>

      <fieldset className="grid gap-6">
        <legend className="mb-4 text-lg font-medium text-primary">{t("optionalSection")}</legend>
        <div className="grid gap-6 sm:grid-cols-2">
          <Field label={t("fields.category_hint")} hint={t("fields.category_hintHint")} error={msg(e.category_hint?.message)} {...form.register("category_hint")} />
          <Field label={t("fields.dimensions_text")} hint={t("fields.dimensions_textHint")} error={msg(e.dimensions_text?.message)} {...form.register("dimensions_text")} />
          <Field label={t("fields.year_text")} inputMode="numeric" error={msg(e.year_text?.message)} {...form.register("year_text")} />
          <Field
            label={t("fields.expected_price")}
            hint={t("fields.expected_priceHint")}
            inputMode="decimal"
            dir="ltr"
            error={msg(e.expected_price?.message)}
            {...form.register("expected_price")}
          />
        </div>
        <TextAreaField label={t("fields.artist_info")} rows={3} error={msg(e.artist_info?.message)} {...form.register("artist_info")} />
        <TextAreaField label={t("fields.customer_notes")} rows={3} error={msg(e.customer_notes?.message)} {...form.register("customer_notes")} />
      </fieldset>

      <div className="flex flex-wrap gap-3 border-t border-border/60 pt-6">
        <Button type="submit" loading={save.isPending} className="min-h-12">
          {save.isPending ? t("submitting") : existing ? t("saveChanges") : t("submit")}
        </Button>
        {existing && onDone ? (
          <Button variant="ghost" onClick={onDone} disabled={save.isPending}>
            {t("cancelEdit")}
          </Button>
        ) : null}
      </div>
    </form>
  );
}
