"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import type { Schema } from "@/lib/api/types";
import { useCurrentUser } from "@/lib/auth/useCurrentUser";

export type Cart = Schema<"Cart">;
export type CartLine = Schema<"CartLine">;

export const cartKey = ["cart"] as const;
export const cartCountKey = ["cart", "count"] as const;

const getCart = () => apiFetch<Cart>("/cart");
const getCount = () => apiFetch<{ count: number }>("/cart/count");

/** Customers only: staff and visitors have no cart (PRD §8). */
export function useIsCustomer() {
  const { data: user, isPending } = useCurrentUser();
  return { isCustomer: Boolean(user && !user.is_staff), user, isPending };
}

export function useCart() {
  const { isCustomer } = useIsCustomer();
  return useQuery({ queryKey: cartKey, queryFn: getCart, enabled: isCustomer });
}

export function useCartCount() {
  const { isCustomer } = useIsCustomer();
  return useQuery({ queryKey: cartCountKey, queryFn: getCount, enabled: isCustomer, staleTime: 30_000 });
}

/** Every cart mutation returns the whole cart: one source of truth, count kept in sync. */
export function useCartMutation<TVars>(fn: (vars: TVars) => Promise<Cart>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (cart) => {
      queryClient.setQueryData(cartKey, cart);
      queryClient.setQueryData(cartCountKey, { count: cart.count });
    },
  });
}

export const addToCart = (vars: { listing: string; quantity: number }) =>
  apiFetch<Cart>("/cart/items", { method: "POST", body: vars });
export const updateLine = (vars: { id: string; quantity: number }) =>
  apiFetch<Cart>(`/cart/items/${vars.id}`, { method: "PATCH", body: { quantity: vars.quantity } });
export const removeLine = (vars: { id: string }) => apiFetch<Cart>(`/cart/items/${vars.id}`, { method: "DELETE" });
export const acceptPrices = () => apiFetch<Cart>("/cart/accept-prices", { method: "POST" });
