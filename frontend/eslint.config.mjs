import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

// RTL rule (ARCHITECTURE §8.3): physical-direction utilities break mirroring.
// Use logical ones instead: ms-/me-/ps-/pe-/start-/end-/text-start/text-end/rounded-s-/border-s-.
const PHYSICAL_DIRECTION =
  "(^|\\s|:)-?(ml|mr|pl|pr|left|right|text-left|text-right|rounded-l|rounded-r|rounded-tl|rounded-tr|rounded-bl|rounded-br|border-l|border-r|scroll-ml|scroll-mr|scroll-pl|scroll-pr)(-|\\s|$)";
const RTL_MESSAGE =
  "Use logical Tailwind utilities (ms-/me-/ps-/pe-/start-/end-/text-start/text-end) — physical directions break RTL.";

const config = [
  { ignores: [".next/**", "node_modules/**", "types/api.d.ts", "next-env.d.ts", "coverage/**"] },
  ...nextVitals,
  ...nextTypescript,
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "no-restricted-syntax": [
        "error",
        { selector: `JSXAttribute[name.name='className'] Literal[value=/${PHYSICAL_DIRECTION}/]`, message: RTL_MESSAGE },
        { selector: `JSXAttribute[name.name='className'] TemplateElement[value.raw=/${PHYSICAL_DIRECTION}/]`, message: RTL_MESSAGE },
      ],
    },
  },
];

export default config;
