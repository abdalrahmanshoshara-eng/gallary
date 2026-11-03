import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const nextConfig: NextConfig = {
  // Self-contained server bundle for the production Docker image.
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  typedRoutes: true,
  // Do not auto-generate AGENTS.md in the repository when the dev server starts.
  agentRules: false,
};

export default withNextIntl(nextConfig);
