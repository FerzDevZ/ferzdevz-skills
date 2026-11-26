---
name: omp-custom-models-setup
description: Configure open.mp custom models correctly.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, models]
    category: samp
---

# open.mp custom models

## When to Use
- Custom models work on 0.3.DL but not open.mp.
- Artwork settings differ from server.cfg.

## 2026 Compatibility & Architecture Matrix
- open.mp supports `AddCharModel`/`AddSimpleModel` with `artwork.enable` in config.json.
- There is no `AddVehicleModel`; vehicles need artconfig/retexture approaches.

## Production Implementation
1. Enable artwork in config.json and set the art path.
2. Register models once at init and verify client download.
3. Check `GetCustomModelPath` when debugging.

```json
{"artwork": {"enable": true, "path": "models"}}
```

## Deprecated Traps & Edge Cases (2026)
- Expecting a vehicle custom-model native that does not exist.
- Registering the same new id twice.

## Verification
- Client downloads and renders the model.
- Registration log shows no failure.
