---
name: omp-json-config-env-vars
description: Use config.json and environment overrides in production.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, config]
    category: samp
---

# config.json production

## When to Use
- Secrets end up in a committed config.json.
- Multiple environments need different settings.

## 2026 Compatibility & Architecture Matrix
- open.mp reads config.json; `--dump-config` converts server.cfg.
- Keys are grouped; `network.*_sync_rate` is read-only at runtime.

## Production Implementation
1. Commit a template with placeholders, generate the real file at deploy.
2. Inject RCON/DB secrets from environment variables in the unit file.
3. Validate by starting the server and grepping for config errors.

```ini
Environment=OMP_RCON_PASSWORD=__FROM_VAULT__
```

## Deprecated Traps & Edge Cases (2026)
- Storing the RCON password in git.
- A key with the wrong case is ignored silently.

## Verification
- Start-up log shows no config error and secrets are absent from the repo.
- Server reports the expected hostname and max players.
