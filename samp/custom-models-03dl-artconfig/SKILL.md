---
name: custom-models-03dl-artconfig
description: Use when 0.3.DL skins or objects fail to download.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, models, artwork]
    category: samp
---

# Ship 0.3.DL models through one registry and the artwork folder

Custom models are two numbers and two files: a base id that also serves as the fallback, a new
id inside a fixed range, and a `.dff` plus `.txd` that the server hands out from the artwork
path. Every failure is one of those four being wrong.

## When to Use

- A custom skin spawns as the base skin for some or all players.
- `AddCharModel` / `AddSimpleModel` returns 0 and nothing is logged.
- The model downloads but is untextured, white, or crashes the client on spawn.
- A new object id collides with an id another filterscript already registered.

## Compatibility & Stack Matrix (2026)

| Item | 0.3.DL R1 / open.mp 1.6.x | SA-MP 0.3.7-R2 |
| --- | --- | --- |
| `AddCharModel` newid | 20001-30000 (10000 slots) | native absent |
| `AddSimpleModel` newid | -1000 to -30000 (29000 slots) | native absent |
| Artwork switch | `artwork.enable` in `config.json` | `useartwork 1` |
| Model folder | `artwork.models_path`, default `models` | `artpath` |
| Fallback model | `baseid`, used when download fails | model does not exist |
| Validity probe | `IsValidCustomModel` (omp 1.1.0.2612+) | none |
| Remote host | `artwork.cdn`, `RedirectDownload` | none |

A 0.3.7-R2 client cannot use any of this: gameplay must tolerate `baseid` being what the
player actually sees.

## Production Implementation

1. Lay the files out flat in the artwork folder. The arguments are file names only, extension
   included, relative to the path in `config.json`; a path separator in the string is a
   download that never resolves. Linux is case-sensitive, so register exactly what `ls` shows.

```bash
mkdir -p models
cp build/lvpdpc2.dff build/lvpdpc2.txd models/
ls -l models/lvpdpc2.dff models/lvpdpc2.txd
```

2. Enable artwork before anything can connect, and point it at the folder you filled:

```json
{
  "artwork": {
    "enable": true,
    "models_path": "models",
    "cdn": ""
  }
}
```

3. Guard the ranges in code rather than by review. Skins are positive 20001-30000, simple
   objects are negative -1000 to -30000, and the two checks are not mirror images.

```pawn
#define CM_SKIN_FIRST  (20001)
#define CM_SKIN_LAST   (30000)
#define CM_OBJ_FIRST   (-1000)
#define CM_OBJ_LAST    (-30000)

stock bool:CM_AddSkin(baseid, newid, const dff[], const txd[])
{
    if (newid < CM_SKIN_FIRST || newid > CM_SKIN_LAST)
    {
        printf("CM reject skin newid=%d", newid);
        return false;
    }
    if (!AddCharModel(baseid, newid, dff, txd))
    {
        printf("CM fail skin newid=%d dff=%s", newid, dff);
        return false;
    }
    return true;
}

stock bool:CM_AddObject(baseid, newid, const dff[], const txd[])
{
    if (newid > CM_OBJ_FIRST || newid < CM_OBJ_LAST)
    {
        printf("CM reject object newid=%d", newid);
        return false;
    }
    return AddSimpleModel(-1, baseid, newid, dff, txd) != 0;
}
```

4. Register everything inside `OnGameModeInit` (or `OnFilterScriptInit`). The natives work
   later, but players already connected when you call them may never receive the download, so
   a `/reloadmodels` command produces exactly the "some players see it" bug.

```pawn
public OnGameModeInit()
{
    CM_AddSkin(305, 20001, "lvpdpc2.dff", "lvpdpc2.txd");
    CM_AddObject(19379, -2000, "wallzzz.dff", "wallzzz.txd");
    printf("CM registered skins=1 objects=1 valid=%d", IsValidCustomModel(20001));
    return 1;
}
```

5. Probe after registration instead of trusting the return values. `IsValidCustomModel` reads
   the server's own table (open.mp 1.1.0.2612+ only, drop the probe on 0.3.DL);
   `GetCustomModelPath` shows the path it will serve.

6. Pin the download cost. Artwork is pushed from the server unless `artwork.cdn` is set, and a
   first join with a large pack stalls at "Connecting". Keep the pack small and use
   `RedirectDownload` when the files live on an HTTP host.

7. Never branch on the custom id for gameplay that must work for everyone. A 0.3.7-R2 client
   and any failed download fall back to `baseid`, so check the model you actually got before
   assuming a rig, a hitbox or a texture exists.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Everyone sees the base skin | `artwork.enable` false, or the file is not in the models folder | enable artwork, correct the path, restart |
| Modelled but untextured | `.txd` missing, or it does not contain the textures the `.dff` names | rebuild the pair together, verify in a TXD viewer |
| Download stalls at connecting | large pack served from the game server | trim the pack, set `artwork.cdn` or `RedirectDownload` |
| `AddCharModel` returns 0 | `newid` outside 20001-30000 | range guard before the call |
| Object appears as its base model | `newid` passed positive, so it landed in skin space | objects use -1000 to -30000 |
| Some players see it, others do not | registration ran after they connected | register in the init callback only |

## Verification

Every `.dff` named in the source must exist in the artwork folder:

```bash
for f in $(grep -rhoE '"[a-z0-9_]+\.dff"' gamemodes/ | tr -d '"' | sort -u); do
  test -f "models/$f" || echo "MISSING $f"
done
```

```text
(no output: every referenced .dff exists)
```

Empty output is the pass. Then the registry itself, from the boot line:

```bash
grep 'CM registered' log.txt | tail -1
```

```text
CM registered skins=12 objects=34 valid=1
```

`valid=1` means `IsValidCustomModel(20001)` found the entry; `valid=0` with a nonzero count
means the model was rejected, and the `CM fail` lines above it name the file.

## Sources (2026)

- https://open.mp/docs/scripting/functions/AddCharModel
- https://open.mp/docs/scripting/functions/AddSimpleModel
- https://open.mp/docs/server/config.json
