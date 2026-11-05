"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { RealtimeSocket, type ConnectionStatus } from "@/lib/realtime/socket";

import { auctionStateKey, getAuctionState } from "./api";
import { applyMessage, OPEN_STATUSES, type AuctionState, type LiveEvent } from "./live";

/**
 * One auction's live state: REST snapshot (with the viewer's own position) kept current by
 * the auction's WebSocket stream. On reconnect or a `seq` gap it resyncs over REST, so the
 * screen never keeps a stale value. Clock: server time, never the device's.
 */
export function useAuctionLive(id: string) {
  const queryClient = useQueryClient();
  const key = auctionStateKey(id);
  const offset = useRef(0);
  const socketRef = useRef<RealtimeSocket | null>(null);
  const [connection, setConnection] = useState<ConnectionStatus>("idle");
  const [lastEvent, setLastEvent] = useState<{ event: LiveEvent; at: number } | null>(null);

  const query = useQuery({
    queryKey: key,
    queryFn: async () => {
      const sentAt = Date.now();
      const state = await getAuctionState(id);
      // Midpoint estimate until the socket's ping/pong gives a better one.
      offset.current = Date.parse(state.server_time) - (sentAt + Date.now()) / 2;
      return state;
    },
    staleTime: 0,
  });
  const { refetch } = query;

  const serverNow = useCallback(() => {
    const clock = socketRef.current?.clock;
    return clock?.hasSample ? clock.now() : Date.now() + offset.current;
  }, []);

  useEffect(() => {
    const socket = new RealtimeSocket({ path: `/ws/auctions/${id}/` });
    socketRef.current = socket;
    const stateKey = auctionStateKey(id);
    const offStatus = socket.onStatus(setConnection);
    const offOpen = socket.onOpen(({ reconnected }) => {
      if (reconnected) void refetch(); // full resync with `me` after any outage
    });
    const offMessage = socket.onMessage((message) => {
      const current = queryClient.getQueryData<AuctionState>(stateKey);
      if (!current) return;
      const result = applyMessage(current, message);
      if (result.kind === "resync") {
        void refetch();
        return;
      }
      if (result.kind !== "applied") return;
      queryClient.setQueryData(stateKey, result.state);
      if (result.event) setLastEvent({ event: result.event, at: Date.now() });
      // Results carry the viewer's outcome (winner, order number): fetch them.
      if (result.event?.type === "status" && !OPEN_STATUSES.has(result.event.status)) void refetch();
    });
    const wake = () => {
      if (document.visibilityState === "visible") {
        socket.reconnectNow();
        void refetch();
      }
    };
    document.addEventListener("visibilitychange", wake);
    window.addEventListener("online", wake);
    socket.start();
    return () => {
      offStatus();
      offOpen();
      offMessage();
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener("online", wake);
      socket.stop();
      socketRef.current = null;
    };
  }, [id, queryClient, refetch]);

  /** Apply the state returned by our own bid immediately (the stream may lag a little). */
  const acceptState = useCallback(
    (state: AuctionState) => {
      const current = queryClient.getQueryData<AuctionState>(auctionStateKey(id));
      if (!current || state.seq >= current.seq) queryClient.setQueryData(auctionStateKey(id), state);
    },
    [id, queryClient],
  );

  return { query, connection, lastEvent, serverNow, acceptState };
}

/** Re-renders every second with the server-corrected time (only the components that need it). */
export function useServerNow(serverNow: () => number, intervalMs = 1000): number {
  const [now, setNow] = useState(serverNow);
  useEffect(() => {
    const timer = setInterval(() => setNow(serverNow()), intervalMs);
    return () => clearInterval(timer);
  }, [serverNow, intervalMs]);
  return now;
}
