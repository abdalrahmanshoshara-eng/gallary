"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { cartCountKey, cartKey, useCart } from "@/features/cart/api";
import { GOVERNORATES } from "@/features/auth/schemas";
import { Link, useRouter } from "@/i18n/navigation";
import { ApiError } from "@/lib/api/errors";
import type { CurrentUser } from "@/lib/auth/types";
import { formatUsd } from "@/lib/formatters/money";
import { applyServerErrors } from "@/lib/forms";

import { checkout, getPolicy, orderKey, ordersKey, policyKey } from "./api";

const schema = z.object({
  governorate: z.string().min(1, "required"),
  city: z.string().trim().min(1, "required").max(100),
  address_line: z.string().trim().min(1, "required").max(255),
  customer_notes: z.string().max(2000),
  accept_policy: z.boolean().refine((v) => v, "policyRequired"),
});
type Values = z.infer<typeof schema>;
const FIELDS = ["governorate", "city", "address_line", "customer_notes", "accept_policy"];
const BACK_TO_CART = new Set(["PRICE_CHANGED", "CHECKOUT_FAILED", "CART_EMPTY"]);

/** One idempotency key per checkout attempt: a double click or a retry after a timeout returns
 *  the same order instead of creating a second one. */
const newKey = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

export function CheckoutForm({ user }: { user: CurrentUser }) {
  const t = useTranslations("checkout");
  const tc = useTranslations("cart");
  const tr = useTranslations("register");
  const tg = useTranslations("governorates");
  const tcommon = useTranslations("common");
  const router = useRouter();
  const queryClient = useQueryClient();
  const uid = useId();
  const [key] = useState(newKey);
  const cart = useCart();
  const policy = useQuery({ queryKey: policyKey, queryFn: getPolicy, staleTime: 5 * 60_000 });
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      governorate: user.governorate ?? "",
      city: user.city ?? "",
      address_line: user.address_line ?? "",
      customer_notes: "",
      accept_policy: false,
    },
  });
  const submit = useMutation({
    mutationFn: (v: Values) => checkout({ ...v, policy_version: policy.data?.version }, key),
    onSuccess: (order) => {
      queryClient.setQueryData(orderKey(order.number), order);
      void queryClient.invalidateQueries({ queryKey: cartKey });
      queryClient.setQueryData(cartCountKey, { count: 0 });
      void queryClient.invalidateQueries({ queryKey: ordersKey });
      router.replace(`/orders/${order.number}?created=1`);
    },
    onError: (error) => {
      if (error instanceof ApiError && BACK_TO_CART.has(error.code)) {
        void queryClient.invalidateQueries({ queryKey: cartKey });
        form.setError("root", { type: error.code, message: error.message });
        return;
      }
      if (error instanceof ApiError && error.code === "POLICY_NOT_ACCEPTED") void policy.refetch();
      applyServerErrors(error, form.setError, FIELDS);
    },
  });
  const e = form.formState.errors;
  const msg = (m?: string) => (m === "required" ? tr("required") : m === "policyRequired" ? t("policyRequired") : m);

  if (cart.isPending || policy.isPending) return <p className="text-muted">{tcommon("loading")}</p>;
  if (cart.isError || policy.isError) return <Alert tone="error">{tcommon("loadError")}</Alert>;
  const data = cart.data;
  if (data.count === 0) {
    return (
      <div className="flex flex-col items-start gap-4">
        <p className="text-muted">{t("emptyRedirect")}</p>
        <Link href="/artworks" className="text-secondary underline">
          {tc("browse")}
        </Link>
      </div>
    );
  }
  if (!data.can_checkout) {
    return (
      <Alert tone="error">
        {data.blocking.includes("price_changed") ? t("priceChanged") : t("unavailable")}{" "}
        <Link href="/cart" className="font-medium underline">
          {t("backToCart")}
        </Link>
      </Alert>
    );
  }
  const lines = data.lines.filter((l) => !l.problem);
  const rootCode = String(e.root?.type ?? "");

  return (
    <form
      noValidate
      onSubmit={form.handleSubmit((v) => submit.mutate(v))}
      className="grid gap-10 pb-28 lg:grid-cols-[minmax(0,1fr)_24rem] lg:pb-0"
    >
      <div className="flex flex-col gap-10">
        {e.root ? (
          <Alert tone="error">
            {e.root.message}{" "}
            {rootCode && BACK_TO_CART.has(rootCode) ? (
              <Link href="/cart" className="font-medium underline">
                {t("backToCart")}
              </Link>
            ) : null}
          </Alert>
        ) : null}

        <section aria-labelledby="co-contact">
          <h2 id="co-contact" className="mb-3 text-lg font-medium text-primary">
            {t("contact")}
          </h2>
          <p className="text-sm">
            {user.display_name} · <bdi dir="ltr">{user.phone}</bdi>
            {user.email ? (
              <>
                {" "}
                · <bdi dir="ltr">{user.email}</bdi>
              </>
            ) : null}
          </p>
          <p className="mt-1 text-xs text-muted">
            {t("contactHint")}{" "}
            <Link href="/account" className="underline">
              {t("accountLink")}
            </Link>
          </p>
        </section>

        <fieldset className="grid gap-6">
          <legend className="mb-1 text-lg font-medium text-primary">{t("delivery")}</legend>
          <p className="-mt-4 text-xs text-muted">{t("deliveryHint")}</p>
          <div className="grid gap-6 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <label htmlFor={`${uid}-gov`} className="text-sm font-medium">
                {tr("governorate")}
              </label>
              <select
                id={`${uid}-gov`}
                className="min-h-11 rounded-[var(--radius-control)] border border-border bg-white px-3"
                aria-invalid={e.governorate ? true : undefined}
                {...form.register("governorate")}
              >
                <option value="">{tr("chooseGovernorate")}</option>
                {GOVERNORATES.map((g) => (
                  <option key={g} value={g}>
                    {tg(g)}
                  </option>
                ))}
              </select>
              {e.governorate ? (
                <p role="alert" className="text-sm text-primary">
                  {msg(e.governorate.message)}
                </p>
              ) : null}
            </div>
            <Field label={tr("city")} autoComplete="address-level2" error={msg(e.city?.message)} {...form.register("city")} />
          </div>
          <Field
            label={tr("addressLine")}
            autoComplete="street-address"
            error={msg(e.address_line?.message)}
            {...form.register("address_line")}
          />
          <label className="flex flex-col gap-2 text-sm font-medium">
            {t("notes")}
            <textarea
              rows={3}
              placeholder={t("notesPlaceholder")}
              className="rounded-[var(--radius-control)] border border-border bg-white px-4 py-3 text-base font-normal"
              {...form.register("customer_notes")}
            />
          </label>
        </fieldset>

        <section aria-labelledby="co-policy" className="rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-6">
          <h2 id="co-policy" className="text-lg font-medium text-primary">
            {policy.data.title}
          </h2>
          <ul className="mt-3 list-inside list-disc space-y-2 text-sm leading-7">
            {policy.data.points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
          <label className="mt-5 flex items-start gap-3 text-sm font-medium">
            <input
              type="checkbox"
              className="mt-1 size-5 accent-[var(--color-primary)]"
              aria-invalid={e.accept_policy ? true : undefined}
              {...form.register("accept_policy")}
            />
            {t("policyAccept")}
          </label>
          {e.accept_policy ? (
            <p role="alert" className="mt-2 text-sm text-primary">
              {msg(e.accept_policy.message)}
            </p>
          ) : null}
        </section>
      </div>

      <aside className="lg:sticky lg:top-24 lg:self-start">
        <section aria-labelledby="co-summary" className="rounded-[var(--radius-card)] border border-border/60 bg-white/60 p-6">
          <h2 id="co-summary" className="text-lg font-medium text-primary">
            {t("items")}
          </h2>
          <ul className="mt-4 flex flex-col gap-3 text-sm">
            {lines.map((line) => (
              <li key={line.id} className="flex justify-between gap-4">
                <span className="min-w-0">
                  {line.title}
                  {line.quantity > 1 ? <span className="text-muted tabular-nums"> × {line.quantity}</span> : null}
                </span>
                <bdi dir="ltr" className="shrink-0">
                  {formatUsd(line.line_total)}
                </bdi>
              </li>
            ))}
          </ul>
          <dl className="mt-5 flex flex-col gap-3 border-t border-border/60 pt-5 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted">{tc("subtotal")}</dt>
              <dd>
                <bdi dir="ltr" className="font-semibold text-primary">
                  {formatUsd(data.subtotal)}
                </bdi>
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="font-medium">{tc("depositNow")}</dt>
              <dd>
                <bdi dir="ltr" className="font-semibold text-primary">
                  {formatUsd(data.deposit_due)}
                </bdi>
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">{tc("rest")}</dt>
              <dd>
                <bdi dir="ltr">{formatUsd(data.remaining_after_deposit)}</bdi>
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-xs text-muted">{t("deadline", { hours: policy.data.reservation_hours })}</p>
          <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border/60 bg-background/95 px-4 py-3 backdrop-blur lg:static lg:mt-6 lg:border-0 lg:bg-transparent lg:p-0">
            <Button type="submit" className="min-h-12 w-full" loading={submit.isPending}>
              {submit.isPending ? t("confirming") : t("confirm")}
            </Button>
          </div>
        </section>
        <Link href="/cart" className="mt-4 inline-block text-sm text-muted hover:text-primary">
          {t("back")}
        </Link>
      </aside>
    </form>
  );
}
