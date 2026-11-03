"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/Button";
import { useRouter } from "@/i18n/navigation";
import { currentUserKey } from "@/lib/auth/useCurrentUser";

import { logout } from "./api";

export function LogoutButton() {
  const t = useTranslations("account");
  const router = useRouter();
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(currentUserKey, null);
      router.replace("/");
      router.refresh();
    },
  });
  return (
    <Button variant="secondary" loading={mutation.isPending} onClick={() => mutation.mutate()}>
      {t("logout")}
    </Button>
  );
}
