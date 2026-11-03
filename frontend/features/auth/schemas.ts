import { z } from "zod";

// Loose client-side checks for fast feedback; the backend normalises and decides (BR-901).
const ARABIC_DIGITS = /[٠-٩]/g;
export const toLatinDigits = (value: string) =>
  value.replace(ARABIC_DIGITS, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));

export const phoneSchema = z.object({
  phone: z
    .string()
    .trim()
    .transform(toLatinDigits)
    .refine((v) => /^\+?[\d\s-]{8,20}$/.test(v), "phoneInvalid"),
});

export const codeSchema = z.object({
  code: z
    .string()
    .trim()
    .transform(toLatinDigits)
    .refine((v) => /^\d{6}$/.test(v), "codeInvalid"),
});

export type PhoneInput = z.input<typeof phoneSchema>;
export type CodeInput = z.input<typeof codeSchema>;
