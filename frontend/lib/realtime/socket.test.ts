import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CloseCode } from "./protocol";
import { RealtimeSocket, socketUrl, type ConnectionStatus } from "./socket";

class FakeSocket {
  static instances: FakeSocket[] = [];
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close(code = 1000) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  receive(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
  drop(code = 1006) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

const latest = () => FakeSocket.instances.at(-1)!;

function makeSocket() {
  const socket = new RealtimeSocket({
    path: "/ws/system/",
    heartbeatIntervalMs: 1000,
    staleAfterMs: 2500,
    backoff: { baseMs: 1000, maxMs: 8000 },
    random: () => 1,
    createSocket: (url) => new FakeSocket(url) as unknown as WebSocket,
  });
  const statuses: ConnectionStatus[] = [];
  socket.onStatus((s) => statuses.push(s));
  return { socket, statuses };
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.instances = [];
});
afterEach(() => vi.useRealTimers());

describe("socketUrl", () => {
  it("uses wss on https and ws on http", () => {
    expect(socketUrl("/ws/x/", { protocol: "https:", host: "art.example" })).toBe("wss://art.example/ws/x/");
    expect(socketUrl("/ws/x/", { protocol: "http:", host: "localhost:8080" })).toBe("ws://localhost:8080/ws/x/");
  });
});

describe("RealtimeSocket", () => {
  it("connects, pings on open and delivers valid messages only", () => {
    const { socket, statuses } = makeSocket();
    const received: string[] = [];
    socket.onMessage((m) => received.push(m.type));
    socket.start();
    latest().open();

    expect(statuses).toEqual(["idle", "connecting", "open"]);
    expect(JSON.parse(latest().sent[0]!)).toMatchObject({ type: "ping" });

    latest().receive({ type: "system.hello", server_time: "2026-11-03T10:00:00Z", data: {} });
    latest().onmessage?.({ data: "garbage" });
    latest().receive({ no: "type" });
    expect(received).toEqual(["system.hello"]);
  });

  it("uses pong messages for clock sync without exposing them", () => {
    const { socket } = makeSocket();
    const received: string[] = [];
    socket.onMessage((m) => received.push(m.type));
    socket.start();
    latest().open();
    latest().receive({ type: "pong", server_time: new Date(Date.now() + 5000).toISOString(), data: { client_time: Date.now() } });
    expect(received).toEqual([]);
    expect(socket.clock.hasSample).toBe(true);
    expect(Math.round(socket.clock.offset / 1000)).toBe(5);
  });

  it("reconnects with backoff and reports reconnection for resync", () => {
    const { socket, statuses } = makeSocket();
    const opens: boolean[] = [];
    socket.onOpen(({ reconnected }) => opens.push(reconnected));
    socket.start();
    latest().open();
    latest().drop();
    expect(statuses.at(-1)).toBe("reconnecting");
    expect(FakeSocket.instances).toHaveLength(1);

    vi.advanceTimersByTime(999);
    expect(FakeSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.instances).toHaveLength(2);
    latest().drop();
    vi.advanceTimersByTime(2000); // second attempt waits base·2
    expect(FakeSocket.instances).toHaveLength(3);
    latest().open();
    expect(opens).toEqual([false, true]);
    expect(statuses.at(-1)).toBe("open");
  });

  it("does not reconnect after terminal close codes or stop()", () => {
    const { socket, statuses } = makeSocket();
    socket.start();
    latest().open();
    latest().drop(CloseCode.SESSION_REVOKED);
    vi.advanceTimersByTime(60_000);
    expect(FakeSocket.instances).toHaveLength(1);
    expect(statuses.at(-1)).toBe("closed");

    const second = makeSocket();
    second.socket.start();
    latest().open();
    second.socket.stop();
    vi.advanceTimersByTime(60_000);
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it("closes a silent (half-open) connection and reconnects", () => {
    const { socket } = makeSocket();
    socket.start();
    latest().open();
    vi.advanceTimersByTime(3000); // no messages for > staleAfterMs
    expect(socket.currentStatus).toBe("reconnecting");
    vi.advanceTimersByTime(1000);
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it("reconnectNow skips the remaining backoff", () => {
    const { socket } = makeSocket();
    socket.start();
    latest().open();
    latest().drop();
    socket.reconnectNow();
    expect(FakeSocket.instances).toHaveLength(2);
  });
});
