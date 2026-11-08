/**
 * One shared `/ws/me/` connection per tab for every feature that listens to the user's
 * private channel (auction notices, the notification bell). Opened on the first subscriber,
 * closed when the last one leaves.
 */
import type { ServerMessage } from "./protocol";
import { RealtimeSocket } from "./socket";

export type MeListener = {
  onMessage?: (message: ServerMessage) => void;
  /** Called on every (re)connection: refetch anything that may have been missed. */
  onOpen?: (info: { reconnected: boolean }) => void;
};

let socket: RealtimeSocket | null = null;
const listeners = new Set<MeListener>();

export function subscribeMe(
  listener: MeListener,
  create: () => RealtimeSocket = () => new RealtimeSocket({ path: "/ws/me/" }),
): () => void {
  listeners.add(listener);
  if (!socket) {
    socket = create();
    socket.onMessage((message) =>
      listeners.forEach((l) => l.onMessage?.(message)),
    );
    socket.onOpen((info) => listeners.forEach((l) => l.onOpen?.(info)));
    socket.start();
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && socket) {
      socket.stop();
      socket = null;
    }
  };
}
