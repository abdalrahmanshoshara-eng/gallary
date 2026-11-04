import { z } from "zod";

// Client-side checks give fast feedback; the backend normalises and decides (BR-901).
// Messages are translation keys resolved by the forms.
const ARABIC_DIGITS = /[٠-٩]/g;
export const toLatinDigits = (value: string) =>
  value.replace(ARABIC_DIGITS, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));

export const phoneField = z
  .string()
  .trim()
  .transform(toLatinDigits)
  .refine((v) => /^\+?[\d\s-]{8,20}$/.test(v), "phoneInvalid");

/** Mirrors the server policy: ≥ 8 characters with a letter and a digit (common/numeric checked server-side). */
export const newPasswordField = z
  .string()
  .min(8, "passwordTooShort")
  .refine((v) => /\p{L}/u.test(v) && /\d/.test(v), "passwordLetterDigit");

export const loginSchema = z.object({
  phone: phoneField,
  password: z.string().min(1, "passwordRequired"),
});

export const GOVERNORATES = [
  "damascus",
  "rif_dimashq",
  "aleppo",
  "homs",
  "hama",
  "latakia",
  "tartus",
  "idlib",
  "daraa",
  "suwayda",
  "quneitra",
  "deir_ez_zor",
  "raqqa",
  "hasakah",
  "outside_syria",
] as const;
export type Governorate = (typeof GOVERNORATES)[number];

const required = (max: number) => z.string().trim().min(1, "required").max(max);

export const registerSchema = z
  .object({
    phone: phoneField,
    first_name: required(60),
    last_name: required(60),
    email: z.email("emailInvalid"),
    governorate: z.union([z.enum(GOVERNORATES), z.literal("")]).refine((v) => v !== "", "required"),
    city: required(100),
    address_line: required(255),
    password: newPasswordField,
    password_confirm: z.string(),
  })
  .refine((v) => v.password === v.password_confirm, { message: "passwordMismatch", path: ["password_confirm"] });

export type LoginValues = z.input<typeof loginSchema>;
export type RegisterValues = z.input<typeof registerSchema>;
