---
name: client-crash-opcode-lookup
description: Turn a client crash into a script or stream cause.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, crash]
    category: samp
---

# client crash triage

## When to Use
- Players crash on entering an area or opening a dialog.
- A crash address repeats across clients.

## 2026 Compatibility & Architecture Matrix
- Client crashes from streamed assets usually name a model or TXD.
- Dialog crashes are often a malformed string or an invalid list item.

## Production Implementation
1. Ask for the client log with the last RPC and model id.
2. Reproduce with one player and bisect the object or dialog dataset.
3. Remove or fix the asset; verify with the same player count.

```bash
grep -iE "model|txd|crash" client_log.txt | tail -20
```

## Deprecated Traps & Edge Cases (2026)
- Blaming the client build before checking the streamed model.
- Sending a dialog string longer than the client buffer.

## Verification
- The reproducing player no longer crashes at that location.
- Crash reports for the signature stop.
