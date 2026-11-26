---
name: amx-decompilation-audit
description: Audit an AMX you did not compile.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, decompile]
    category: samp
---

# AMX audit

## When to Use
- A third-party filterscript or gamemode must be reviewed before running.
- You need to confirm which natives a binary actually calls.

## 2026 Compatibility & Architecture Matrix
- An AMX is bytecode; decompilers approximate source and can be wrong.
- Use the native table and string table as ground truth, not the decompiled text.

## Production Implementation
1. Extract the native list and strings from the AMX.
2. Compare every native against your server build's functions.
3. Treat anything that writes files or opens sockets as untrusted.

```bash
strings filterscript.amx | sort -u | head -50
```

## Deprecated Traps & Edge Cases (2026)
- Decompiled output can invent control flow; do not patch from it blindly.
- An AMX built for 0.3.7 may call natives absent on open.mp.

## Verification
- Native list matches includes available on the server.
- The script runs in a sandbox with no unexpected file writes.
