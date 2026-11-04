"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { useRouter } from "@/i18n/navigation";

import {
  artworkKey,
  createArtwork,
  listTerms,
  termsKey,
  updateArtwork,
  type AdminArtwork,
  type AdminCategory,
  type AdminTerm,
  type TermKind,
} from "./api";
import { ArtistPicker } from "./ArtistPicker";
import { applyServerErrors, emptyToNull } from "./form-utils";

const decimal = z.string().refine((v) => v === "" || (/^\d{1,6}(\.\d{1,2})?$/.test(v) && Number(v) > 0), "number");
const schema = z
  .object({
    title: z.string().trim().min(1, "required").max(250),
    description: z.string(),
    category: z.string().min(1, "required"),
    artist: z.string(),
    creator_name_override: z.string().max(200),
    executor: z.string(),
    owner_name: z.string().max(200),
    rights_holder: z.string().max(200),
    materials: z.array(z.number()),
    techniques: z.array(z.number()),
    tags: z.array(z.number()),
    height_cm: decimal,
    width_cm: decimal,
    depth_cm: decimal,
    weight_kg: decimal,
    year_created: z.string().refine((v) => v === "" || (/^\d{3,4}$/.test(v) && Number(v) <= 2100), "year"),
    internal_notes: z.string(),
  })
  .refine((v) => v.artist !== "" || v.creator_name_override.trim() !== "", {
    message: "creator",
    path: ["artist"],
  });
type Values = z.infer<typeof schema>;
const FIELDS = [
  "title",
  "description",
  "category",
  "artist",
  "creator_name_override",
  "executor",
  "owner_name",
  "rights_holder",
  "materials",
  "techniques",
  "tags",
  "height_cm",
  "width_cm",
  "depth_cm",
  "weight_kg",
  "year_created",
  "internal_notes",
];

const textareaClass =
  "min-h-32 rounded-[var(--radius-control)] border border-border bg-white px-4 py-3 text-base focus:border-secondary focus:outline-none";
const selectClass = "min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3";
const fieldsetClass = "grid gap-6";
const legendClass = "mb-4 text-lg font-medium text-primary";

function defaults(a?: AdminArtwork): Values {
  return {
    title: a?.title ?? "",
    description: a?.description ?? "",
    category: a?.category ? String(a.category) : "",
    artist: a?.artist ?? "",
    creator_name_override: a?.creator_name_override ?? "",
    executor: a?.executor ?? "",
    owner_name: a?.owner_name ?? "",
    rights_holder: a?.rights_holder ?? "",
    materials: a?.materials ?? [],
    techniques: a?.techniques ?? [],
    tags: a?.tags ?? [],
    height_cm: a?.height_cm ?? "",
    width_cm: a?.width_cm ?? "",
    depth_cm: a?.depth_cm ?? "",
    weight_kg: a?.weight_kg ?? "",
    year_created: a?.year_created ? String(a.year_created) : "",
    internal_notes: a?.internal_notes ?? "",
  };
}

function toBody(v: Values) {
  return {
    ...v,
    category: Number(v.category),
    artist: emptyToNull(v.artist),
    executor: emptyToNull(v.executor),
    height_cm: emptyToNull(v.height_cm),
    width_cm: emptyToNull(v.width_cm),
    depth_cm: emptyToNull(v.depth_cm),
    weight_kg: emptyToNull(v.weight_kg),
    year_created: v.year_created ? Number(v.year_created) : null,
  };
}

/** Parents first, each followed by its subcategories; inactive ones only if already chosen. */
export function orderCategories(categories: AdminCategory[], selected?: number) {
  const usable = categories.filter((c) => c.is_active !== false || c.id === selected);
  const roots = usable.filter((c) => c.parent == null);
  return roots.flatMap((root) => [
    { category: root, depth: 0 },
    ...usable.filter((c) => c.parent === root.id).map((category) => ({ category, depth: 1 })),
  ]);
}

function TermChecklist({
  kind,
  legend,
  value,
  onChange,
}: {
  kind: Exclude<TermKind, "categories">;
  legend: string;
  value: number[];
  onChange: (value: number[]) => void;
}) {
  const terms = useQuery({ queryKey: termsKey(kind), queryFn: () => listTerms<AdminTerm>(kind) });
  const visible = (terms.data ?? []).filter((term) => term.is_active !== false || value.includes(term.id));
  if (terms.data && visible.length === 0) return null;
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{legend}</legend>
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {visible.map((term) => (
          <label key={term.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-[var(--color-primary)]"
              checked={value.includes(term.id)}
              onChange={(e) => onChange(e.target.checked ? [...value, term.id] : value.filter((id) => id !== term.id))}
            />
            {term.name}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function ArtworkForm({ artwork }: { artwork?: AdminArtwork }) {
  const t = useTranslations("admin.artworks");
  const ta = useTranslations("admin.artists");
  const tc = useTranslations("common");
  const router = useRouter();
  const queryClient = useQueryClient();
  const categories = useQuery({
    queryKey: termsKey("categories"),
    queryFn: () => listTerms<AdminCategory>("categories"),
  });
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults(artwork) });
  const save = useMutation({
    mutationFn: (values: Values) =>
      artwork ? updateArtwork(artwork.id, toBody(values)) : createArtwork(toBody(values)),
    onSuccess: (saved) => {
      queryClient.setQueryData(artworkKey(saved.id), saved);
      void queryClient.invalidateQueries({ queryKey: ["admin", "artworks"] });
      if (!artwork) {
        router.replace(`/admin/artworks/${saved.id}?created=1`);
        return;
      }
      form.reset(defaults(saved));
    },
    onError: (error) => applyServerErrors(error, form.setError, FIELDS),
  });
  const e = form.formState.errors;
  const msg = (m?: string) =>
    m === "required"
      ? tc("required")
      : m === "number"
        ? tc("invalidNumber")
        : m === "year"
          ? t("invalidYear")
          : m === "creator"
            ? t("creatorOrArtist")
            : m;
  const selectedCategory = artwork?.category;
  const uid = useId();

  return (
    <form noValidate onSubmit={form.handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-10">
      {save.isSuccess && artwork && !form.formState.isDirty ? <Alert tone="success">{t("saved")}</Alert> : null}
      {e.root ? <Alert tone="error">{e.root.message}</Alert> : null}

      <fieldset className={fieldsetClass}>
        <legend className={legendClass}>{t("basics")}</legend>
        <Field label={t("titleField")} error={msg(e.title?.message)} {...form.register("title")} />
        <label className="flex flex-col gap-2 text-sm font-medium">
          {t("description")}
          <textarea className={textareaClass} {...form.register("description")} />
        </label>
        <div className="flex flex-col gap-2 text-sm">
          <label htmlFor={`${uid}-category`} className="font-medium">
            {t("category")}
          </label>
          <select
            id={`${uid}-category`}
            className={selectClass}
            aria-invalid={e.category ? true : undefined}
            aria-describedby={e.category ? `${uid}-category-error` : undefined}
            {...form.register("category")}
          >
            <option value="">{t("chooseCategory")}</option>
            {orderCategories(categories.data ?? [], selectedCategory).map(({ category, depth }) => (
              <option key={category.id} value={String(category.id)}>
                {depth ? `— ${category.name}` : category.name}
              </option>
            ))}
          </select>
          {e.category ? (
            <span id={`${uid}-category-error`} role="alert" className="text-sm text-primary">
              {msg(e.category.message)}
            </span>
          ) : null}
        </div>
      </fieldset>

      <fieldset className={fieldsetClass}>
        <legend className={legendClass}>{t("attribution")}</legend>
        <Controller
          control={form.control}
          name="artist"
          render={({ field }) => (
            <ArtistPicker
              label={t("artist")}
              emptyLabel={t("noArtist")}
              searchPlaceholder={ta("searchPlaceholder")}
              hiddenLabel={ta("statusHidden")}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
        {e.artist ? (
          <p role="alert" className="-mt-4 text-sm text-primary">
            {msg(e.artist.message)}
          </p>
        ) : null}
        <Field
          label={t("creatorOverride")}
          error={msg(e.creator_name_override?.message)}
          {...form.register("creator_name_override")}
        />
        <Controller
          control={form.control}
          name="executor"
          render={({ field }) => (
            <ArtistPicker
              label={t("executor")}
              emptyLabel={t("noExecutor")}
              searchPlaceholder={ta("searchPlaceholder")}
              hiddenLabel={ta("statusHidden")}
              value={field.value}
              onChange={field.onChange}
            />
          )}
        />
        <div className="grid gap-6 md:grid-cols-2">
          <Field label={t("ownerName")} error={msg(e.owner_name?.message)} {...form.register("owner_name")} />
          <Field
            label={t("rightsHolder")}
            error={msg(e.rights_holder?.message)}
            {...form.register("rights_holder")}
          />
        </div>
        {artwork?.owner_user_phone ? (
          <p className="text-sm text-muted">
            {t("ownerUser")}: <span dir="ltr">{artwork.owner_user_phone}</span>
          </p>
        ) : null}
      </fieldset>

      <fieldset className={fieldsetClass}>
        <legend className={legendClass}>{t("classification")}</legend>
        {(["materials", "techniques", "tags"] as const).map((kind) => (
          <Controller
            key={kind}
            control={form.control}
            name={kind}
            render={({ field }) => (
              <TermChecklist kind={kind} legend={t(kind)} value={field.value} onChange={field.onChange} />
            )}
          />
        ))}
      </fieldset>

      <fieldset className={fieldsetClass}>
        <legend className={legendClass}>{t("physical")}</legend>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-5">
          {(
            [
              ["height_cm", "height"],
              ["width_cm", "width"],
              ["depth_cm", "depth"],
              ["weight_kg", "weight"],
            ] as const
          ).map(([name, label]) => (
            <Field
              key={name}
              label={t(label)}
              inputMode="decimal"
              dir="ltr"
              error={msg(e[name]?.message)}
              {...form.register(name)}
            />
          ))}
          <Field
            label={t("year")}
            inputMode="numeric"
            dir="ltr"
            error={msg(e.year_created?.message)}
            {...form.register("year_created")}
          />
        </div>
      </fieldset>

      <fieldset className="grid gap-6 rounded-[var(--radius-card)] border border-border/60 p-6">
        <legend className="px-2 text-lg font-medium text-primary">{t("internal")}</legend>
        <textarea
          aria-label={t("internal")}
          className={textareaClass}
          {...form.register("internal_notes")}
        />
      </fieldset>

      <div>
        <Button type="submit" loading={save.isPending} disabled={artwork ? !form.formState.isDirty : false}>
          {save.isPending ? tc("saving") : artwork ? tc("save") : t("createDraft")}
        </Button>
      </div>
    </form>
  );
}
