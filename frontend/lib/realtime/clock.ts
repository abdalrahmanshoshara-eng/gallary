/**
 * Estimates the offset between the browser clock and the server clock from ping/pong
 * round trips (NTP-style). The sample with the lowest round-trip time wins because it
 * has the smallest error bound. Used for countdown display only — never for decisions.
 */
export class ServerClock {
  private offsetMs = 0;
  private bestRttMs = Number.POSITIVE_INFINITY;

  /** @param sentAt client ms when ping was sent, @param receivedAt client ms when pong arrived */
  addSample(sentAt: number, serverTimeIso: string, receivedAt: number): void {
    const serverMs = Date.parse(serverTimeIso);
    const rtt = receivedAt - sentAt;
    if (Number.isNaN(serverMs) || rtt < 0) return;
    if (rtt <= this.bestRttMs) {
      this.bestRttMs = rtt;
      this.offsetMs = serverMs - (sentAt + rtt / 2);
    }
  }

  /** Offset to add to Date.now() to approximate server time. */
  get offset(): number {
    return this.offsetMs;
  }

  get hasSample(): boolean {
    return Number.isFinite(this.bestRttMs);
  }

  now(clientNow: number = Date.now()): number {
    return clientNow + this.offsetMs;
  }
}
