---
name: custom-dff-txd-model-converter-pipeline
description: Use when custom DFF/TXD models fail to download.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, models, artwork, dl]
    category: samp
---

# Custom DFF/TXD pipeline: one registry, verified pairs, gated spawns

## When to Use

- A custom object shows the stock shape, shows nothing, or flickers only for some players.
- Players stall at "downloading models" or crash right after connecting.
- You have Texture Studio output and need it as a downloadable 0.3.DL model instead of a stock id swap.

## Compatibility & Stack Matrix (2026)

| Piece | 2026 reality | What it means in practice |
| --- | --- | --- |
| Id space | `AddSimpleModel` newid range is -1000 to -30000 | allocate from one manifest, never type ids at call sites |
| Config gate | `artwork.enable` (default `true`), `artwork.models_path` (default `models`), `artwork.cdn` for remote hosting | with artwork disabled every registration is a silent no-op |
| `baseid` | stock model used when the download fails, and the shape the client falls back to | pick a base whose footprint matches the mesh |
| Registration point | `OnGameModeInit` / `OnFilterScriptInit` | models registered later are missed by players already connected |
| Arrival signal | `OnPlayerFinishedDownloading(playerid, virtualworld)` | spawn custom ids for a player only after this fires |
| Mobile client | tighter texture budget than PC | keep power-of-two maps, 1024 max on the long edge |
| Linux host | case-sensitive filesystem | `wallzzz.dff` and `Wallzzz.DFF` are different files to `omp-server` |

## Production Implementation

1. Start with a manifest, because an id typed twice is an id collision nobody finds until players see the wrong building. Keep the CSV in the repo next to the assets and mirror it into one Pawn table:

```pawn
// models/manifest.csv -> id,baseid,dff,txd,project
// -2000,19379,wallzzz.dff,wallzzz.txd,turf_wall
// -2001,19471,kiosk.dff,kiosk.txd,corner_kiosk
#define MODEL_COUNT 2
new const g_ModelId[MODEL_COUNT]   = { -2000, -2001 };
new const g_ModelBase[MODEL_COUNT] = { 19379, 19471 };
new const g_ModelDff[MODEL_COUNT][] = { "wallzzz.dff", "kiosk.dff" };
new const g_ModelTxd[MODEL_COUNT][] = { "wallzzz.txd", "kiosk.txd" };
```

2. Author in the tool that owns each step, and do not let one tool pretend to do another:
   - Texture Studio for object placement and the material list; it exports the object code and the texture names it expects.
   - TXD Workshop or Magic.TXD to build the texture library itself, one library per model set.
   - 3ds Max with Kam's GTA scripts (or ZModeler) to export the `.dff`. One clump per model, no separate collision export: with `AddSimpleModel` the client keeps the `baseid` collision, so a mesh with a different footprint clips.

3. Normalise names before they ever reach the server: lowercase ASCII, no spaces, no directory separators, and the exact same stem in the manifest, the DFF and the TXD. Then check the pair on the deployment filesystem, not on the workstation:

```bash
ls -1 models/ | sort | awk '{print tolower($0)}' | uniq -d
```

4. Budget textures, not polygons. A 2048x2048 uncompressed map that looks fine on PC is the usual reason a mobile client fails the download or drops to the base model. Power-of-two, 1024 maximum on the long edge, DXT1 when there is no alpha, DXT5 when there is.

5. Register inside `OnGameModeInit` and check both the return value and the id, because a failed registration does not throw: it returns 0 and leaves players with the base model.

```pawn
public OnGameModeInit()
{
    new registered = 0;
    for (new i = 0; i < MODEL_COUNT; i++)
    {
        if (!AddSimpleModel(-1, g_ModelBase[i], g_ModelId[i], g_ModelDff[i], g_ModelTxd[i]))
        {
            printf("[models] FAIL id=%d dff=%s txd=%s", g_ModelId[i], g_ModelDff[i], g_ModelTxd[i]);
            continue;
        }
        if (!IsValidCustomModel(g_ModelId[i]))
            printf("[models] WARN id=%d registered but not valid", g_ModelId[i]);
        else registered++;
    }
    printf("[models] registered=%d/%d", registered, MODEL_COUNT);
    return 1;
}
```

6. Gate custom spawns on the download callback. Until a player reports the world as downloaded, give them the `baseid` object so they see a building instead of a hole:

```pawn
new bool:g_ModelsReady[MAX_PLAYERS];

public OnPlayerFinishedDownloading(playerid, virtualworld)
{
    g_ModelsReady[playerid] = true;
    printf("[models] player=%d world=%d downloaded", playerid, virtualworld);
    return 1;
}
stock Models_Place(playerid, index, Float:x, Float:y, Float:z)
{
    new model = g_ModelsReady[playerid] ? g_ModelId[index] : g_ModelBase[index];
    return CreatePlayerObject(playerid, model, x, y, z, 0.0, 0.0, 0.0);
}
```

7. Log the download duration per player. A model that is missing or corrupt on the client does not raise an error on the server; it shows up as a long or stuck gap between connect and `OnPlayerFinishedDownloading`, which is the only server-side evidence you get.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Everyone sees the base object | `artwork.enable` false, or a failed `AddSimpleModel` return ignored | enable artwork, log the return as in step 5 |
| Works on Windows dev, not on the Linux host | filename case or path separator mismatch | lowercase names, verified with the `awk` check in step 3 |
| Player crashes on connect | TXD too large for the client, or a DFF with more than one clump | shrink to 1024/DXT and re-export from 3ds Max |
| Hole in the map for late joiners | custom object spawned before `OnPlayerFinishedDownloading` | gate on `g_ModelsReady`, fall back to `baseid` |
| Model id collides with another set | ids hand-typed in two files | single manifest, grep the whole source for the id |
| Object invisible but collision present | mesh exported without matching the base footprint | choose a `baseid` with the same ground shape |

## Verification

```bash
python3 - <<'PY'
import csv, pathlib, sys
rows = list(csv.DictReader(open("models/manifest.csv")))
bad = [r for r in rows if not (pathlib.Path("models", r["dff"]).is_file() and pathlib.Path("models", r["txd"]).is_file())]
print(f"models={len(rows)} missing_pairs={len(bad)}")
sys.exit(1 if bad else 0)
PY
grep -c "AddSimpleModel" gamemodes/models.pwn
```

Expected: `models=2 missing_pairs=0` and exit 0, so every manifest row has both files on the host the server reads; the grep returns `1` (the single call site inside the loop). In game the log must show `[models] registered=2/2`, and a fresh client that connects shows `[models] player=N world=0 downloaded` within a few seconds and renders the mesh, not the base object.

## Sources (2026)

- https://open.mp/docs/scripting/functions/AddSimpleModel
- https://open.mp/docs/scripting/callbacks/OnPlayerFinishedDownloading
- https://open.mp/docs/scripting/functions/IsValidCustomModel
