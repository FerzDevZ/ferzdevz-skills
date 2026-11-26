---
name: custom-dff-txd-model-converter-pipeline
description: Ship custom DFF/TXD without breaking clients.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, models]
    category: samp
---

# DFF/TXD pipeline

## When to Use
- Custom models fail to download or crash the client.
- Texture names or dimensions exceed limits.

## 2026 Compatibility & Architecture Matrix
- 0.3.DL custom models need DFF+TXD pairs; mobile clients have stricter limits.
- Texture size should stay within 512–1024 for compatibility.

## Production Implementation
1. Validate DFF/TXD in a model viewer and keep texture names short.
2. Register ids at init and test a fresh client download.
3. Log download failures per model id.

```pawn
AddSimpleModel(-1, 19379, -2000, "custom.dff", "custom.txd");
```

## Deprecated Traps & Edge Cases (2026)
- Shipping PC-sized textures to mobile clients.
- Reusing an existing model id instead of a new one.

## Verification
- Fresh client downloads and renders the model; no crash on spawn.
