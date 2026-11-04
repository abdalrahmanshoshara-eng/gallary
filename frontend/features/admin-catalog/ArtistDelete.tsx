"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { useRouter } from "@/i18n/navigation";

import { deleteArtist } from "./api";
import { errorText } from "@/lib/forms";

/** Deletion is refused by the API (409) while the artist has artworks; the message explains why. */
export function ArtistDelete({ id, name }: { id: string; name: string }) {
  const t = useTranslations("admin.artists");
  const router = useRouter();
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: () => deleteArtist(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "artists"] });
      router.replace("/admin/artists");
    },
  });
  return (
    <div className="flex flex-col gap-3">
      {remove.error ? <Alert tone="error">{errorText(remove.error)}</Alert> : null}
      <div>
        <Button
          variant="ghost"
          loading={remove.isPending}
          onClick={() => {
            if (window.confirm(`${name}: ${t("confirmDelete")}`)) remove.mutate();
          }}
        >
          {t("deleteArtist")}
        </Button>
      </div>
    </div>
  );
}
