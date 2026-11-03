import createMiddleware from "next-intl/middleware";

import { routing } from "./i18n/routing";

// Next.js 16 "proxy" (formerly middleware): locale negotiation only.
// It is not a security boundary — authorisation is enforced by the Django API.
export default createMiddleware(routing);

export const config = {
  // Skip API/WebSocket paths (served by Django via nginx), Next internals, health and files.
  matcher: ["/((?!api|ws|internal-admin|_next|_vercel|healthz|.*\\..*).*)"],
};
