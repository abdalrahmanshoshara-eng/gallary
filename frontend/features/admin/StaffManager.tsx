"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ApiError } from "@/lib/api/errors";
import type { RoleName } from "@/lib/auth/types";

import { createStaff, listStaff, revokeStaff, staffKey, updateStaff, type AdminUser } from "./api";
import { RoleCheckboxes } from "./RoleCheckboxes";

const errorText = (error: unknown) => (error instanceof ApiError ? error.message : null);

function AddStaffForm() {
  const t = useTranslations("admin.staff");
  const queryClient = useQueryClient();
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [roles, setRoles] = useState<RoleName[]>([]);
  const [errors, setErrors] = useState<{ phone?: string; name?: string; roles?: string; form?: string }>({});

  const mutation = useMutation({
    mutationFn: createStaff,
    onSuccess: () => {
      setPhone("");
      setName("");
      setRoles([]);
      void queryClient.invalidateQueries({ queryKey: staffKey });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "INVALID_PHONE") setErrors({ phone: error.message });
      else if (error instanceof ApiError && error.code === "NAME_REQUIRED") setErrors({ name: error.message });
      else setErrors({ form: errorText(error) ?? undefined });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const next: typeof errors = {};
    if (!phone.trim()) next.phone = t("phone");
    if (!name.trim()) next.name = t("nameRequired");
    if (roles.length === 0) next.roles = t("rolesRequired");
    setErrors(next);
    if (Object.keys(next).length === 0) mutation.mutate({ phone, display_name: name, roles });
  }

  return (
    <form noValidate onSubmit={submit} className="grid gap-6 rounded-[var(--radius-card)] border border-border/60 p-6">
      <h2 className="text-lg font-medium text-primary">{t("add")}</h2>
      {mutation.isSuccess ? <Alert tone="success">{t("created")}</Alert> : null}
      {errors.form ? <Alert tone="error">{errors.form}</Alert> : null}
      <div className="grid gap-6 md:grid-cols-2">
        <Field label={t("phone")} type="tel" dir="ltr" value={phone} error={errors.phone} onChange={(e) => setPhone(e.target.value)} />
        <Field label={t("name")} value={name} error={errors.name} onChange={(e) => setName(e.target.value)} />
      </div>
      <RoleCheckboxes legend={t("roles")} value={roles} onChange={setRoles} error={errors.roles} />
      <div>
        <Button type="submit" loading={mutation.isPending}>
          {t("add")}
        </Button>
      </div>
    </form>
  );
}

function StaffRow({ member, currentUserId }: { member: AdminUser; currentUserId: string }) {
  const t = useTranslations("admin.staff");
  const tr = useTranslations("admin.roles");
  const tc = useTranslations("common");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [roles, setRoles] = useState<RoleName[]>(member.roles as RoleName[]);
  const isSelf = member.id === currentUserId;
  const refresh = () => void queryClient.invalidateQueries({ queryKey: staffKey });

  const save = useMutation({ mutationFn: () => updateStaff(member.id, { roles }), onSuccess: () => { setEditing(false); refresh(); } });
  const revoke = useMutation({ mutationFn: () => revokeStaff(member.id), onSuccess: refresh });

  return (
    <li className="flex flex-col gap-4 py-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="font-medium">
            {member.display_name || "—"} {isSelf ? <span className="text-sm text-muted">{t("you")}</span> : null}
            {!member.is_active ? <span className="ms-2 text-xs text-primary">{t("inactive")}</span> : null}
          </p>
          <p className="text-sm text-muted">
            <bdi dir="ltr">{member.phone}</bdi> · {member.roles.map((r) => tr(r as RoleName)).join("، ")}
          </p>
        </div>
        {!isSelf ? (
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setEditing((v) => !v)}>
              {editing ? tc("cancel") : t("editRoles")}
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(true)}>
              {t("revoke")}
            </Button>
          </div>
        ) : null}
      </div>
      {save.isError || revoke.isError ? <Alert tone="error">{errorText(save.error ?? revoke.error)}</Alert> : null}
      {editing ? (
        <div className="flex flex-col gap-4">
          <RoleCheckboxes legend={t("roles")} value={roles} onChange={setRoles} error={roles.length ? undefined : t("rolesRequired")} />
          <div>
            <Button loading={save.isPending} disabled={roles.length === 0} onClick={() => save.mutate()}>
              {tc("save")}
            </Button>
          </div>
        </div>
      ) : null}
      {confirming ? (
        <Alert tone="info">
          <span>{t("revokeConfirm", { name: member.display_name || member.phone })}</span>
          <span className="ms-4 inline-flex gap-2">
            <Button variant="primary" loading={revoke.isPending} onClick={() => revoke.mutate()}>
              {tc("yes")}
            </Button>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              {tc("no")}
            </Button>
          </span>
        </Alert>
      ) : null}
    </li>
  );
}

export function StaffManager({ currentUserId }: { currentUserId: string }) {
  const t = useTranslations("admin.staff");
  const tc = useTranslations("common");
  const staff = useQuery({ queryKey: staffKey, queryFn: listStaff });

  return (
    <div className="flex flex-col gap-10">
      <AddStaffForm />
      {staff.isPending ? <p className="text-muted">{tc("loading")}</p> : null}
      {staff.isError ? <Alert tone="error">{tc("loadError")}</Alert> : null}
      {staff.data ? (
        staff.data.length ? (
          <ul className="divide-y divide-border/60 border-y border-border/60">
            {staff.data.map((member) => (
              <StaffRow key={member.id} member={member} currentUserId={currentUserId} />
            ))}
          </ul>
        ) : (
          <p className="text-muted">{t("empty")}</p>
        )
      ) : null}
    </div>
  );
}
