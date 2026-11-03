/**
 * Resilient WebSocket connection: automatic reconnect with jittered backoff, heartbeat
 * with dead-connection detection, server clock estimation and status reporting.
 *
 * It is a transport only. Ordering (`seq`), gap detection and state resync are feature
 * concerns built on top of it (auction live state, Phase 6). Bids never travel through
 * the socket — they are HTTP requests (ADR-10).
 */
import { backoffDelay, DEFAULT_BACKOFF, type BackoffOptions } from "./backoff";
import { ServerClock } from "./clock";
import { serverMessageSchema, TERMINAL_CLOSE_CODES, type ServerMessage } from "./protocol";

export type ConnectionStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed";

export type RealtimeSocketOptions = {
  /** Path such as "/ws/system/"; resolved against the current origin (ws:// or wss://). */
  path: string;
  heartbeatIntervalMs?: number;
  /** Close and reconnect if no message arrives within this window. */
  staleAfterMs?: number;
  backoff?: BackoffOptions;
  /** Injected for tests. */
  createSocket?: (url: string) => WebSocket;
  random?: () => number;
};

type MessageListener = (message: ServerMessage) => void;
type StatusListener = (status: ConnectionStatus) => void;
type OpenListener = (info: { reconnected: boolean }) => void;

export function socketUrl(path: string, location: Pick<Location, "protocol" | "host"> = window.location): string {
  const scheme = location.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${location.host}${path}`;
}

export class RealtimeSocket {
  readonly clock = new ServerClock();
  private socket: WebSocket | null = null;
  private status: ConnectionStatus = "idle";
  private attempt = 0;
  private everOpened = false;
  private stopped = true;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private lastMessageAt = 0;
  private readonly messageListeners = new Set<MessageListener>();
  private readonly statusListeners = new Set<StatusListener>();
  private readonly openListeners = new Set<OpenListener>();
  private readonly options: Required<Omit<RealtimeSocketOptions, "createSocket" | "random">> &
    Pick<RealtimeSocketOptions, "createSocket" | "random">;

  constructor(options: RealtimeSocketOptions) {
    this.options = {
      heartbeatIntervalMs: 25_000,
      staleAfterMs: 60_000,
      backoff: DEFAULT_BACKOFF,
      ...options,
    };
  }

  get currentStatus(): ConnectionStatus {
    return this.status;
  }

  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    this.clearTimers();
    const socket = this.socket;
    this.socket = null;
    socket?.close(1000);
    this.setStatus("closed");
  }

  /** Reconnect immediately (e.g. on `online` or when the tab becomes visible again). */
  reconnectNow(): void {
    if (this.stopped || this.status === "open" || this.status === "connecting") return;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.connect();
  }

  onMessage(listener: MessageListener): () => void {
    this.messageListeners.add(listener);
    return () => this.messageListeners.delete(listener);
  }

  onStatus(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.status);
    return () => this.statusListeners.delete(listener);
  }

  /** Fires on every successful (re)connection — the hook for resyncing state. */
  onOpen(listener: OpenListener): () => void {
    this.openListeners.add(listener);
    return () => this.openListeners.delete(listener);
  }

  private connect(): void {
    this.setStatus(this.everOpened ? "reconnecting" : "connecting");
    const url = socketUrl(this.options.path);
    const socket = this.options.createSocket ? this.options.createSocket(url) : new WebSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      if (this.socket !== socket) return;
      const reconnected = this.everOpened;
      this.everOpened = true;
      this.attempt = 0;
      this.lastMessageAt = Date.now();
      this.setStatus("open");
      this.startHeartbeat();
      this.sendPing();
      for (const listener of this.openListeners) listener({ reconnected });
    };

    socket.onmessage = (event: MessageEvent) => {
      if (this.socket !== socket) return;
      this.lastMessageAt = Date.now();
      const message = this.parse(event.data);
      if (!message) return;
      if (message.type === "pong") {
        const sentAt = message.data["client_time"];
        if (typeof sentAt === "number") this.clock.addSample(sentAt, message.server_time, Date.now());
        return;
      }
      for (const listener of this.messageListeners) listener(message);
    };

    socket.onclose = (event: CloseEvent) => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.clearTimers();
      if (this.stopped || TERMINAL_CLOSE_CODES.has(event.code)) {
        this.stopped = true;
        this.setStatus("closed");
        return;
      }
      this.scheduleReconnect();
    };

    // Errors are always followed by `close`, which drives reconnection.
    socket.onerror = () => undefined;
  }

  private parse(data: unknown): ServerMessage | null {
    if (typeof data !== "string") return null;
    try {
      const result = serverMessageSchema.safeParse(JSON.parse(data));
      return result.success ? result.data : null;
    } catch {
      return null;
    }
  }

  private scheduleReconnect(): void {
    this.setStatus("reconnecting");
    const delay = backoffDelay(this.attempt, this.options.backoff, this.options.random);
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.stopped) this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (Date.now() - this.lastMessageAt > this.options.staleAfterMs) {
        // Half-open connection: force a close so the reconnect path takes over.
        this.socket?.close(4000);
        return;
      }
      this.sendPing();
    }, this.options.heartbeatIntervalMs);
  }

  private sendPing(): void {
    if (this.socket?.readyState === 1) {
      this.socket.send(JSON.stringify({ type: "ping", client_time: Date.now() }));
    }
  }

  private clearTimers(): void {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.heartbeatTimer = null;
    this.reconnectTimer = null;
  }

  private setStatus(status: ConnectionStatus): void {
    if (this.status === status) return;
    this.status = status;
    for (const listener of this.statusListeners) listener(status);
  }
}
