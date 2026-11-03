"use client";

import { useTranslations } from "next-intl";

import { ROLES, type RoleName } from "@/lib/auth/types";

export function RoleCheckboxes({
  value,
  onChange,
  legend,
  error,
}: {
  value: RoleName[];
  onChange: (roles: RoleName[]) => void;
  legend: string;
  error?: string;
}) {
  const t = useTranslations("admin.roles");
  return (
    <fieldset className="flex flex-col gap-2" aria-invalid={error ? true : undefined}>
      <legend className="mb-2 text-sm font-medium">{legend}</legend>
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {ROLES.map((role) => (
          <label key={role} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-[var(--color-primary)]"
              checked={value.includes(role)}
              onChange={(e) => onChange(e.target.checked ? [...value, role] : value.filter((r) => r !== role))}
            />
            {t(role)}
          </label>
        ))}
      </div>
      {error ? (
        <p role="alert" className="text-sm text-primary">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
