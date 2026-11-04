"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { useRouter } from "@/i18n/navigation";

import { artistKey, createArtist, updateArtist, type AdminArtist } from "./api";
import { applyServerErrors } from "@/lib/forms";

const schema = z.object({
  name: z.string().trim().min(1, "required").max(200),
  biography: z.string(),
  city: z.string().max(100),
  birth_year: z.string().refine((v) => v === "" || (/^\d{4}$/.test(v) && Number(v) >= 1800 && Number(v) <= 2100), "year"),
  status: z.enum(["active", "hidden"]),
  is_featured: z.boolean(),
  contact_phone: z.string().max(32),
  contact_email: z.union([z.literal(""), z.email("email")]),
  internal_notes: z.string(),
});
type Values = z.infer<typeof schema>;
const FIELDS = Object.keys(schema.shape);

const textareaClass =
  "min-h-32 rounded-[var(--radius-control)] border border-border bg-white px-4 py-3 text-base focus:border-secondary focus:outline-none";

export function ArtistForm({ artist }: { artist?: AdminArtist }) {
  const t = useTranslations("admin.artists");
  const tc = useTranslations("common");
  const router = useRouter();
  const queryClient = useQueryClient();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: artist?.name ?? "",
      biography: artist?.biography ?? "",
      city: artist?.city ?? "",
      birth_year: artist?.birth_year ? String(artist.birth_year) : "",
      status: (artist?.status as Values["status"]) ?? "active",
      is_featured: artist?.is_featured ?? false,
      contact_phone: artist?.contact_phone ?? "",
      contact_email: artist?.contact_email ?? "",
      internal_notes: artist?.internal_notes ?? "",
    },
  });
  const save = useMutation({
    mutationFn: (values: Values) => {
      const body = { ...values, birth_year: values.birth_year ? Number(values.birth_year) : null };
      return artist ? updateArtist(artist.id, body) : createArtist(body);
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(artistKey(saved.id), saved);
      void queryClient.invalidateQueries({ queryKey: ["admin", "artists"] });
      if (!artist) {
        router.replace(`/admin/artists/${saved.id}`);
        return;
      }
      form.reset(form.getValues());
    },
    onError: (error) => applyServerErrors(error, form.setError, FIELDS),
  });
  const e = form.formState.errors;
  const msg = (m?: string) =>
    m === "required" ? tc("required") : m === "year" ? t("invalidYear") : m === "email" ? tc("invalidEmail") : m;

  return (
    <form noValidate onSubmit={form.handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-10">
      {save.isSuccess && artist && !form.formState.isDirty ? <Alert tone="success">{t("saved")}</Alert> : null}
      {e.root ? <Alert tone="error">{e.root.message}</Alert> : null}

      <fieldset className="grid gap-6">
        <legend className="mb-4 text-lg font-medium text-primary">{t("publicSection")}</legend>
        <Field label={t("name")} error={e.name && msg(e.name.message)} {...form.register("name")} />
        <label className="flex flex-col gap-2 text-sm font-medium">
          {t("biography")}
          <textarea className={textareaClass} {...form.register("biography")} />
        </label>
        <div className="grid gap-6 md:grid-cols-2">
          <Field label={t("city")} {...form.register("city")} />
          <Field label={t("birthYear")} inputMode="numeric" dir="ltr" error={e.birth_year && msg(e.birth_year.message)} {...form.register("birth_year")} />
        </div>
        <div className="flex flex-wrap items-center gap-8 text-sm">
          <label className="flex items-center gap-2">
            {t("visibility")}
            <select className="min-h-10 rounded-[var(--radius-control)] border border-border bg-white px-3" {...form.register("status")}>
              <option value="active">{t("statusActive")}</option>
              <option value="hidden">{t("statusHidden")}</option>
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" className="size-4 accent-[var(--color-primary)]" {...form.register("is_featured")} />
            {t("isFeatured")}
          </label>
        </div>
      </fieldset>

      <fieldset className="grid gap-6 rounded-[var(--radius-card)] border border-border/60 p-6">
        <legend className="px-2 text-lg font-medium text-primary">{t("internalSection")}</legend>
        <div className="grid gap-6 md:grid-cols-2">
          <Field label={t("contactPhone")} type="tel" dir="ltr" {...form.register("contact_phone")} />
          <Field label={t("contactEmail")} type="email" dir="ltr" error={e.contact_email && msg(e.contact_email.message)} {...form.register("contact_email")} />
        </div>
        <label className="flex flex-col gap-2 text-sm font-medium">
          {t("notes")}
          <textarea className={textareaClass} {...form.register("internal_notes")} />
        </label>
      </fieldset>

      <div>
        <Button type="submit" loading={save.isPending} disabled={artist ? !form.formState.isDirty : false}>
          {save.isPending ? tc("saving") : artist ? tc("save") : tc("create")}
        </Button>
      </div>
    </form>
  );
}
