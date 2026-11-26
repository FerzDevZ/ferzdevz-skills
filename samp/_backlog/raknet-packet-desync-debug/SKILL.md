---
name: raknet-packet-desync-debug
description: Debug RPC desync between client and server.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, network]
    category: samp
---

# RPC desync

## When to Use
- A feature works for some clients and not others.
- The server logs show malformed packet reads.

## 2026 Compatibility & Architecture Matrix
- open.mp supports 0.3.7 clients while `network.allow_037_clients` is true; RPC layouts differ across builds.
- Pawn.RakNet 1.6.0-omp can log incoming ids and sizes.

## Production Implementation
1. Log RPC id, size and first bytes per player for a short window.
2. Compare with the client build's expected layout.
3. Drop packets that fail a length check instead of half-applying.

```pawn
public OnIncomingPacket(playerid, packetid, BitStream:bs) {
    new len = BS_GetNumberOfBitsUsed(bs);
    printf("rpc=%d bits=%d", packetid, len);
    return 1;
}
```

## Deprecated Traps & Edge Cases (2026)
- Guessing field order from memory instead of a capture.
- Applying a packet partially when a read fails.

## Verification
- The logged size matches the documented layout for the client build.
- No malformed-read warnings under normal play.
