---
name: omp-custom-models-setup
description: Use when open.mp artwork models never reach clients.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, models, artwork]
    category: samp
---

# Wire open.mp custom models: artwork block, id ranges, one probe

`config.json` decides whether models are served; the natives decide which ids exist. Neither
reports failure loudly: a missing switch shows the base model, a bad id does nothing.

## When to Use

- A `.dff`/`.txd` pair sits in `/models` but every player still sees the base skin or object.
- You are porting a 0.3.DL server (`useartwork`/`artpath`) and need the exact open.mp keys.
- Two systems register the same `newid` and one model wins at random.
- The model appears for players who joined before a restart, never for players who join after.
- You need to prove what the server actually registered, not what the source says.

## Compatibility & Stack Matrix (2026)

| Item | Value | Notes |
| --- | --- | --- |
| Server | open.mp 1.6.x (`config.json`) | legacy 0.3.DL R1 uses `server.cfg` |
| Enable switch | `artwork.enable` | artwork is not served while this is false |
| Models folder | `artwork.models_path` | default `models`, relative to the server root |
| Remote models | `artwork.cdn` | HTTP address of a remote model server |
| Embedded serving | `artwork.port`, `artwork.web_server_bind` | open.mp hosts the download webserver |
| Skin ids | `AddCharModel` 20001-30000 | 10000 slots, used with `SetPlayerSkin` |
| Object ids | `AddSimpleModel` -1000 to -30000 | 29000 slots, used with `CreateObject` |
| Vehicle ids | none | no native registers a custom vehicle model |
| Probe | `IsValidCustomModel`, `GetCustomModelPath` | open.mp 1.1.0.2612 and newer |

The artwork block has exactly five documented keys (`enable`, `models_path`, `cdn`, `port`,
`web_server_bind`); registration is the native call, there is no `artconfig.json` in open.mp.
A 0.3.7-R2 client cannot use artwork at all and must see `baseid`.

## Production Implementation

1. Put the pair in one folder, flat and with exact case. Linux is case-sensitive, and the
   native takes a file name, not a path:

```bash
mkdir -p models && cp build/lvpdpc2.dff build/lvpdpc2.txd models/
ls -l models/lvpdpc2.dff models/lvpdpc2.txd
```

2. Enable artwork before the first join, and keep the download off the game port when the host
   already uses it:

```json
{
  "network": { "port": 7777 },
  "artwork": {
    "enable": true,
    "models_path": "models",
    "cdn": "",
    "port": 8080,
    "web_server_bind": ""
  }
}
```

3. Register every id inside `OnGameModeInit`, from one table, with range and duplicate checks in
   the same place. A negative `newid` passed to `AddCharModel` is the classic silent no-op:

```pawn
#define CM_SKIN_FIRST (20001)
#define CM_SKIN_LAST  (30000)

new gCMUsed[64];
new gCMCount;

stock bool:CM_AddSkin(baseid, newid, const dff[], const txd[])
{
    if (newid < CM_SKIN_FIRST || newid > CM_SKIN_LAST)
    {
        printf("[cm] reject skin newid=%d out of range", newid);
        return false;
    }
    for (new i = 0; i < gCMCount; i++)
        if (gCMUsed[i] == newid) return false;
    if (!AddCharModel(baseid, newid, dff, txd)) return false;
    gCMUsed[gCMCount++] = newid;
    return true;
}
```

4. Register objects through the same guard, in the negative space. `AddSimpleModel` takes the
   virtual world first; `-1` means every world, and a real world id delays the download:

```pawn
stock bool:CM_AddObject(baseid, newid, const dff[], const txd[])
{
    if (newid > -1000 || newid < -30000) return false;
    return AddSimpleModel(-1, baseid, newid, dff, txd) != 0;
}

public OnGameModeInit()
{
    CM_AddSkin(305, 20001, "lvpdpc2.dff", "lvpdpc2.txd");
    CM_AddObject(19379, -2000, "wallzzz.dff", "wallzzz.txd");
    return 1;
}
```

5. Probe once, after registration, and log the path you expect. It is the only way to tell "the
   native rejected it" from "the client did not download it":

```pawn
new dff[64], txd[64];
GetCustomModelPath(20001, dff, sizeof dff, txd, sizeof txd);
printf("[cm] ready skins=%d valid=%d dff=%s", gCMCount, IsValidCustomModel(20001), dff);
```

6. Do not offer a `/reloadmodels` command. The natives work at any time, but players already
   connected when you call them may never receive the download - the documented failure that
   looks like "it works for new players only".

7. Keep the first-join cost down. Served locally, artwork is pushed through the download
   webserver on first connect, so a large pack stalls at "Connecting"; move the files to an
   HTTP host and set `artwork.cdn` instead of growing the pack.

8. Never branch gameplay on a custom id without a fallback: a 0.3.7-R2 client, a disabled
   artwork block and a failed download all resolve to `baseid`, so the skin may be 305.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Everyone sees the base skin | `artwork.enable` false, or file missing from `artwork.models_path` | enable artwork, fix the path, restart |
| `AddCharModel` returns 0 with a valid-looking id | `newid` outside 20001-30000 | range guard before the call |
| Object shows its base model | `newid` passed positive, landing in skin space | objects are -1000 to -30000 |
| Untextured or white model | `.txd` missing or lacks textures the `.dff` references | rebuild the pair, re-export together |
| `valid=0` after a successful return | id overwritten by a second registration, or wrong file case | dedupe the table, `ls` the exact case |
| Works for new joins only | registration ran outside the init callback | register in `OnGameModeInit` only |
| Stuck at "Connecting" | pack served from the game server on a slow link | trim the pack or set `artwork.cdn` |

## Verification

Every file name in the source must exist in the artwork folder, and the boot line is the
registration receipt:

```bash
for f in $(grep -rhoE '"[a-z0-9_]+\.dff"' gamemodes/ | tr -d '"' | sort -u); do
  test -f "models/$f" || echo "MISSING $f"
done
grep '\[cm\] ready' server/log.txt | tail -1
```

```text
[cm] ready skins=12 valid=1 dff=models/lvpdpc2.dff
```

No `MISSING` line, and `valid=1` proves `IsValidCustomModel(20001)` found the entry. `valid=0`
with a nonzero count means the native took the call but the id is not registered; the
`[cm] reject` line above it names the reason.

## Sources (2026)

- https://open.mp/docs/server/config.json
- https://open.mp/docs/scripting/functions/AddCharModel
- https://open.mp/docs/scripting/functions/AddSimpleModel
