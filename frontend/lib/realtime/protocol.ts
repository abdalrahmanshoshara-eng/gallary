import { z } from "zod";

/** Server → client envelope (ARCHITECTURE §5.4). `seq` is present on ordered stream messages. */
export const serverMessageSchema = z.object({
  type: z.string(),
  server_time: z.string(),
  seq: z.number().int().nonnegative().optional(),
  data: z.record(z.string(), z.unknown()).default({}),
});

export type ServerMessage = z.infer<typeof serverMessageSchema>;

/** Application close codes (mirrors apps/realtime/protocol.py). */
export const CloseCode = {
  NORMAL: 1000,
  SERVICE_RESTART: 1012,
  UNAUTHORIZED: 4401,
  FORBIDDEN: 4403,
  NOT_FOUND: 4404,
  SESSION_REVOKED: 4409,
} as const;

/** Closes after which reconnecting cannot succeed. */
export const TERMINAL_CLOSE_CODES: ReadonlySet<number> = new Set([
  CloseCode.UNAUTHORIZED,
  CloseCode.FORBIDDEN,
  CloseCode.NOT_FOUND,
  CloseCode.SESSION_REVOKED,
]);
