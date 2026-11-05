"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useId, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ResponsiveImage } from "@/components/art/ResponsiveImage";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, TextAreaField } from "@/components/ui/Field";
import { useRouter } from "@/i18n/navigation";
import { fromDamascusInput, toDamascusInput } from "@/lib/formatters/datetime";
import { applyServerErrors } from "@/lib/forms";

import {
  adminAuctionKey,
  createAuction,
  getAdminRequest,
  listEligibleArtworks,
  updateAuction,
  type AdminAuction,
  type EligibleArtwork,
} from "./api";

const money = (optional = false) =>
  z
    .string()
    .trim()
    .refine((v) => (optional && v === "") || (/^\d{1,10}(\.\d{1,2})?$/.test(v) && Number(v) > 0), "money");
const whole = (min: number, max: number) =>
  z
    .string()
    .trim()
    .refine((v) => /^\d+$/.test(v) && Number(v) >= min && Number(v) <= max, "range");

const schema = z
  .object({
    title: z.string().trim().max(250),
    terms: z.string().trim().max(5000),
    starting_price: money(),
    minimum_increment: money(),
    reserve_price: money(true),
    starts_at: z.string().refine((v) => fromDamascusInput(v) !== null, "required"),
    ends_at: z.string().refine((v) => fromDamascusInput(v) !== null, "required"),
    extension_window_min: whole(0, 60),
    extension_duration_min: whole(0, 60),
    max_extensions: whole(0, 50),
    winner_deposit_percent: z
      .string()
      .trim()
      .refine((v) => /^\d{1,3}(\.\d{1,2})?$/.test(v) && Number(v) >= 50 && Number(v) <= 100, "deposit"),
    non_payment_policy: z.enum(["offer_next_bidder", "cancel_award"]),
    commission_rate: z
      .string()
      .trim()
      .refine((v) => v === "" || (/^\d{1,3}(\.\d{1,2})?$/.test(v) && Number(v) <= 100), "range"),
  })
  .refine((v) => (fromDamascusInput(v.ends_at) ?? "") > (fromDamascusInput(v.starts_at) ?? ""), { path: ["ends_at"], message: "order" })
  .refine((v) => v.reserve_price === "" || Number(v.reserve_price) >= Number(v.starting_price), {
    path: ["reserve_price"],
    message: "reserve",
  });
type Values = z.infer<typeof schema>;

const SERVER_FIELDS: Record<string, keyof Values> = {
  title: "title",
  terms: "terms",
  starting_price: "starting_price",
  minimum_increment: "minimum_increment",
  reserve_price: "reserve_price",
  starts_at: "starts_at",
  ends_at: "ends_at",
  extension_window_sec: "extension_window_min",
  extension_duration_sec: "extension_duration_min",
  max_extensions: "max_extensions",
  winner_deposit_percent: "winner_deposit_percent",
  non_payment_policy: "non_payment_policy",
  commission_rate: "commission_rate",
};

function defaults(auction?: AdminAuction): Values {
  const start = new Date(Date.now() + 24 * 3600 * 1000);
  start.setUTCMinutes(0, 0, 0);
  const end = new Date(start.getTime() + 3 * 24 * 3600 * 1000);
  return {
    title: auction?.title ?? "",
    terms: auction?.terms ?? "",
    starting_price: auction ? String(Number(auction.starting_price)) : "",
    minimum_increment: auction ? String(Number(auction.minimum_increment)) : "",
    reserve_price: auction?.reserve_price ? String(Number(auction.reserve_price)) : "",
    starts_at: toDamascusInput(auction?.starts_at ?? start.toISOString()),
    ends_at: toDamascusInput(auction?.ends_at ?? end.toISOString()),
    extension_window_min: String((auction?.extension_window_sec ?? 300) / 60),
    extension_duration_min: String((auction?.extension_duration_sec ?? 300) / 60),
    max_extensions: String(auction?.max_extensions ?? 10),
    winner_deposit_percent: auction ? String(Number(auction.winner_deposit_percent)) : "50",
    non_payment_policy: auction?.non_payment_policy ?? "offer_next_bidder",
    commission_rate: auction?.commission_rate ? String(Number(auction.commission_rate)) : "",
  };
}

function toBody(v: Values, includeCommission: boolean) {
  return {
    title: v.title || undefined,
    terms: v.terms,
    starting_price: v.starting_price,
    minimum_increment: v.minimum_increment,
    reserve_price: v.reserve_price || null,
    starts_at: fromDamascusInput(v.starts_at),
    ends_at: fromDamascusInput(v.ends_at),
    extension_window_sec: Number(v.extension_window_min) * 60,
    extension_duration_sec: Number(v.extension_duration_min) * 60,
    max_extensions: Number(v.max_extensions),
    winner_deposit_percent: v.winner_deposit_percent,
    non_payment_policy: v.non_payment_policy,
    ...(includeCommission ? { commission_rate: v.commission_rate || null } : {}),
  };
}

function ArtworkPicker({ value, onChange }: { value: EligibleArtwork | null; onChange: (a: EligibleArtwork | null) => void }) {
  const t = useTranslations("admin.auctions");
  const id = useId();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);
  const results = useQuery({
    queryKey: ["admin", "auctions", "eligible", debounced],
    queryFn: () => listEligibleArtworks(debounced),
    enabled: value === null,
  });

  if (value) {
    return (
      <div className="flex items-center gap-4 rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-3">
        <div className="size-16 shrink-0 overflow-hidden rounded-[var(--radius-control)] bg-surface/60 p-1">
          {value.image ? <ResponsiveImage image={value.image.image} alt="" sizes="4rem" /> : null}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-primary">{value.title}</p>
          <p className="truncate text-sm text-muted">{value.creator_name}</p>
        </div>
        <Button variant="ghost" onClick={() => onChange(null)}>
          {t("change")}
        </Button>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <label htmlFor={id} className="text-sm font-medium">
        {t("artwork")}
      </label>
      <input
        id={id}
        type="search"
        placeholder={t("artworkSearch")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
        aria-describedby={`${id}-hint`}
      />
      <p id={`${id}-hint`} className="text-xs text-muted">
        {t("artworkHint")}
      </p>
      <ul className="max-h-80 divide-y divide-border/50 overflow-y-auto rounded-[var(--radius-card)] border border-border/60" aria-busy={results.isFetching || undefined}>
        {results.data?.results.length === 0 ? <li className="p-4 text-sm text-muted">{t("noArtworks")}</li> : null}
        {results.data?.results.map((artwork) => (
          <li key={artwork.id}>
            <button type="button" onClick={() => onChange(artwork)} className="flex w-full items-center gap-3 p-3 text-start hover:bg-surface/50">
              <span className="size-12 shrink-0 overflow-hidden rounded-[var(--radius-control)] bg-surface/60 p-1">
                {artwork.image ? <ResponsiveImage image={artwork.image.image} alt="" sizes="3rem" /> : null}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-primary">{artwork.title}</span>
                <span className="block truncate text-xs text-muted">{artwork.creator_name}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Create an auction (draft) or edit its terms before it starts. Times are entered in
 * Damascus time; amounts in USD. From an auction request the artwork and the agreed
 * commission are fixed by the request.
 */
export function AuctionForm({ auction, requestId, onSaved }: { auction?: AdminAuction; requestId?: string; onSaved?: () => void }) {
  const t = useTranslations("admin.auctions");
  const tc = useTranslations("common");
  const router = useRouter();
  const queryClient = useQueryClient();
  const [artwork, setArtwork] = useState<EligibleArtwork | null>(null);
  const [artworkError, setArtworkError] = useState(false);
  const [saved, setSaved] = useState(false);
  const request = useQuery({
    queryKey: ["admin", "auction-request", requestId ?? ""],
    queryFn: () => getAdminRequest(requestId!),
    enabled: Boolean(requestId),
  });
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults(auction) });
  const fromRequest = request.data;

  useEffect(() => {
    if (fromRequest && !form.getValues("title")) form.setValue("title", fromRequest.work_title);
  }, [fromRequest, form]);

  const save = useMutation({
    mutationFn: (values: Values) => {
      if (auction) return updateAuction(auction.id, toBody(values, false));
      const artworkId = fromRequest?.artwork_id ?? artwork?.id;
      return createAuction({ ...toBody(values, !fromRequest), artwork: artworkId, request: fromRequest?.id ?? null });
    },
    onSuccess: (result) => {
      queryClient.setQueryData(adminAuctionKey(result.id), result);
      void queryClient.invalidateQueries({ queryKey: ["admin", "auctions"] });
      if (auction) {
        setSaved(true);
        onSaved?.();
      } else {
        router.push(`/admin/auctions/${result.id}?created=1`);
      }
    },
    onError: (error) => {
      const fields = Object.keys(SERVER_FIELDS);
      applyServerErrors(error, (name, err) => form.setError((SERVER_FIELDS[name as string] ?? name) as keyof Values, err), fields);
    },
  });

  const e = form.formState.errors;
  const msg = (m?: string) =>
    m === "money"
      ? tc("invalidNumber")
      : m === "range"
        ? tc("invalidNumber")
        : m === "deposit"
          ? t("errors.deposit")
          : m === "order"
            ? t("errors.order")
            : m === "reserve"
              ? t("errors.reserve")
              : m === "required"
                ? tc("required")
                : m;
  const needsArtwork = !auction && !requestId;
  const sectionTitle = "mb-4 text-lg font-medium text-primary";

  return (
    <form
      noValidate
      className="flex flex-col gap-10"
      onSubmit={form.handleSubmit((values) => {
        if (needsArtwork && !artwork) return setArtworkError(true);
        setSaved(false);
        save.mutate(values);
      })}
    >
      {e.root ? <Alert tone="error">{e.root.message}</Alert> : null}
      {saved ? <Alert tone="success">{t("saved")}</Alert> : null}

      {!auction ? (
        <section>
          <h2 className={sectionTitle}>{t("sections.artwork")}</h2>
          {requestId ? (
            fromRequest ? (
              <Alert tone="info">{t("fromRequest", { title: fromRequest.work_title, rate: String(Number(fromRequest.agreed_commission_rate ?? 0)) })}</Alert>
            ) : (
              <div className="h-16 animate-pulse rounded-[var(--radius-card)] bg-surface/60" />
            )
          ) : (
            <>
              <ArtworkPicker
                value={artwork}
                onChange={(a) => {
                  setArtwork(a);
                  setArtworkError(false);
                  if (a && !form.getValues("title")) form.setValue("title", a.title);
                }}
              />
              {artworkError ? (
                <p role="alert" className="mt-2 text-sm text-primary">
                  {tc("required")}
                </p>
              ) : null}
            </>
          )}
        </section>
      ) : null}

      <fieldset className="grid gap-6">
        <legend className={sectionTitle}>{t("sections.pricing")}</legend>
        <Field label={t("fields.title")} hint={t("fields.titleHint")} error={msg(e.title?.message)} {...form.register("title")} />
        <div className="grid gap-6 sm:grid-cols-2">
          <Field label={t("fields.starting_price")} inputMode="decimal" dir="ltr" required error={msg(e.starting_price?.message)} {...form.register("starting_price")} />
          <Field label={t("fields.minimum_increment")} inputMode="decimal" dir="ltr" required error={msg(e.minimum_increment?.message)} {...form.register("minimum_increment")} />
          <Field
            label={t("fields.reserve_price")}
            hint={t("fields.reserve_priceHint")}
            inputMode="decimal"
            dir="ltr"
            error={msg(e.reserve_price?.message)}
            {...form.register("reserve_price")}
          />
          {!auction && !requestId ? (
            <Field
              label={t("fields.commission_rate")}
              hint={t("fields.commission_rateHint")}
              inputMode="decimal"
              dir="ltr"
              error={msg(e.commission_rate?.message)}
              {...form.register("commission_rate")}
            />
          ) : null}
        </div>
      </fieldset>

      <fieldset className="grid gap-6">
        <legend className={sectionTitle}>{t("sections.timing")}</legend>
        <div className="grid gap-6 sm:grid-cols-2">
          <Field label={t("fields.starts_at")} hint={t("fields.timeHint")} type="datetime-local" dir="ltr" required error={msg(e.starts_at?.message)} {...form.register("starts_at")} />
          <Field label={t("fields.ends_at")} hint={t("fields.timeHint")} type="datetime-local" dir="ltr" required error={msg(e.ends_at?.message)} {...form.register("ends_at")} />
        </div>
      </fieldset>

      <fieldset className="grid gap-6">
        <legend className={sectionTitle}>{t("sections.rules")}</legend>
        <div className="grid gap-6 sm:grid-cols-3">
          <Field label={t("fields.extension_window_sec")} inputMode="numeric" dir="ltr" error={msg(e.extension_window_min?.message)} {...form.register("extension_window_min")} />
          <Field label={t("fields.extension_duration_sec")} inputMode="numeric" dir="ltr" error={msg(e.extension_duration_min?.message)} {...form.register("extension_duration_min")} />
          <Field label={t("fields.max_extensions")} inputMode="numeric" dir="ltr" error={msg(e.max_extensions?.message)} {...form.register("max_extensions")} />
        </div>
        <div className="grid gap-6 sm:grid-cols-2">
          <Field
            label={t("fields.winner_deposit_percent")}
            hint={t("fields.winner_deposit_percentHint")}
            inputMode="decimal"
            dir="ltr"
            error={msg(e.winner_deposit_percent?.message)}
            {...form.register("winner_deposit_percent")}
          />
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium">{t("fields.non_payment_policy")}</legend>
            {(["offer_next_bidder", "cancel_award"] as const).map((policy) => (
              <label key={policy} className="flex min-h-11 items-center gap-3 text-sm">
                <input type="radio" value={policy} className="size-4 accent-[var(--color-primary)]" {...form.register("non_payment_policy")} />
                {t(`policy.${policy}`)}
              </label>
            ))}
          </fieldset>
        </div>
        <TextAreaField label={t("fields.terms")} rows={4} error={msg(e.terms?.message)} {...form.register("terms")} />
      </fieldset>

      <div className="border-t border-border/60 pt-6">
        <Button type="submit" loading={save.isPending} className="min-h-12">
          {auction ? tc("save") : t("saveDraft")}
        </Button>
      </div>
    </form>
  );
}
