---
name: interior-exterior-portal-streaming
description: Use when door teleports show a void or pop-in objects.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, streamer, interiors, portals]
    category: samp
---

# Move and re-stream in one call, and pre-warm before the player crosses

A door transition is two client events: the position/interior change, and the streamer
re-evaluating what that player may see. Wrong order and the client spends one or two frames
inside geometry it has not received — the black void. `Streamer_UpdateEx` collapses both:
it sets the position and re-streams around it, with an optional freeze released only when
the destination is loaded.

## When to Use

- A player sees a black void or the wrong room for a moment at a door.
- Interior furniture pops in after arrival, sometimes a second late.
- Players fall through the floor right after a teleport.
- A vehicle stays on the street while the driver is inside.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 / SA-MP 0.3.7-R2 | 256 interiors, 2,147,483,647 worlds |
| Streamer | 2.9.6, `#include <streamer>` | `Streamer_Update` and `Streamer_UpdateEx` |
| `Streamer_UpdateEx` | `playerid, Float:x, Float:y, Float:z, worldid, interiorid, type, compensatedtime, freezeplayer` | nine positional arguments |
| `compensatedtime` = -1 | re-streams around the point, does **not** move the player | the pre-warm mode |
| `compensatedtime` >= 0 | performs the teleport | `0` = move immediately |
| `freezeplayer` = 1 | frozen until the streamer finishes, then released | `0` for pre-warm |
| `type` = -1 | every item type | narrow it only when profiling |

## Production Implementation

1. Store both sides of every door as one row, so a transition is symmetric and the exit
   cannot drift from the entrance. Interior ids are validated at load, not at teleport:

```pawn
#include <openmp>
#include <streamer>

#define MAX_PORTALS (48)

enum E_Portal
{
    ptName[24],
    Float:ptOutX, Float:ptOutY, Float:ptOutZ, ptOutWorld, ptOutInterior,
    Float:ptInX,  Float:ptInY,  Float:ptInZ,  ptInWorld,  ptInInterior
};

new gPortal[MAX_PORTALS][E_Portal];
new gPortalCount;
new gPortalAt[MAX_PLAYERS];
new gPortalTick[MAX_PLAYERS];
```

   Rows are parsed once with `sscanf(line, "s[24]fffddfffdd", ...)`; a row whose interior id
   exceeds 255 is dropped at load, because above that the client never switches interior.

2. Pre-warm while the player is still walking. `compensatedtime -1` re-streams the
   destination chunk without touching the player position, so the objects arrive before the
   door is used. Run it on approach, not every tick:

```pawn
stock PortalWarm(playerid, idx)
{
    if (idx < 0 || idx >= gPortalCount) return 0;
    if (!IsPlayerInRangeOfPoint(playerid, 25.0, gPortal[idx][ptOutX],
                                gPortal[idx][ptOutY], gPortal[idx][ptOutZ]))
        return 0;

    Streamer_UpdateEx(playerid, gPortal[idx][ptInX], gPortal[idx][ptInY],
        gPortal[idx][ptInZ], gPortal[idx][ptInWorld], gPortal[idx][ptInInterior],
        -1, -1, 0);                                   // no move, no freeze
    return 1;
}
```

3. Transition in one call: ids first, vehicle linked, then a single `Streamer_UpdateEx`
   with `compensatedtime 0` and `freezeplayer 1`. The freeze is what prevents the
   fall-through frame:

```pawn
stock PortalEnter(playerid, idx)
{
    if (idx < 0 || idx >= gPortalCount) return 0;

    new vehicleid = GetPlayerVehicleID(playerid);
    SetPlayerInterior(playerid, gPortal[idx][ptInInterior]);
    SetPlayerVirtualWorld(playerid, gPortal[idx][ptInWorld]);

    if (vehicleid != 0)
    {
        LinkVehicleToInterior(vehicleid, gPortal[idx][ptInInterior]);
        SetVehicleVirtualWorld(vehicleid, gPortal[idx][ptInWorld]);
    }

    gPortalAt[playerid] = idx;
    gPortalTick[playerid] = GetTickCount();

    Streamer_UpdateEx(playerid, gPortal[idx][ptInX], gPortal[idx][ptInY],
        gPortal[idx][ptInZ], gPortal[idx][ptInWorld], gPortal[idx][ptInInterior],
        -1, 0, 1);                                    // move now, freeze until streamed

    SetTimerEx("PortalRelease", 2000, false, "i", playerid);   // safety net
    return 1;
}

public PortalRelease(playerid)
{
    if (!IsPlayerConnected(playerid)) return 0;
    TogglePlayerControllable(playerid, true);
    printf("[portal] %d %s %dms", playerid, gPortal[gPortalAt[playerid]][ptName],
           GetTickCount() - gPortalTick[playerid]);
    return 1;
}
```

4. Keep the safety timer: `freezeplayer 1` is released when the last item arrives, and if
   the plugin never ticked, nothing releases it — a two-second `TogglePlayerControllable`
   covers that case.

5. Make pre-warm cheap: call `PortalWarm` from a one-second timer that only fires when no
   portal is active, or from the door checkpoint. Per-tick calls multiply streamer work by
   the tick rate for no gain.

6. Fix pop-in at its source: an exterior building needs a `streamdistance` larger than the
   distance it is first visible from, with its LOD inside that radius.
7. Log the transition with `GetTickCount`: twenty `ms` values answer "slow or empty".

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| One or two frames of black void | position applied before interior/world | set ids first, then `Streamer_UpdateEx` |
| Objects appear after arrival | no pre-warm and stream distance below the corridor length | `PortalWarm` at 25 m, raise `streamdistance` |
| Player stuck with no controls | `freezeplayer 1` never released | keep the `PortalRelease` safety timer |
| Vehicle left outside | `LinkVehicleToInterior` missing | link the vehicle before the move |
| Street visible from inside | objects created with `interiorid -1` | pass the real interior id |
| Falls through the floor at the door | unfrozen before the destination shell streamed | keep the freeze, do not `TogglePlayerControllable` early |
| Exterior facade vanishes at the door | LOD `drawdistance` below the stream distance | raise both on the building objects |

## Verification

Transition latency is measured from the log the code already writes:

```bash
awk '/^\[portal\]/ { for (i = 1; i <= NF; i++) if ($i ~ /ms$/) { v = $i + 0; if (v > max) max = v; n++; if (v > 400) slow++ } } END { print "transitions", n, "max_ms", max, "over_400ms", slow+0 }' portal.log
```

Expected after 20 door uses:

```text
transitions 20 max_ms 214 over_400ms 0
```

`over_400ms 0` means no transition exceeded the budget where a freeze becomes visible; a
non-zero `slow` with a normal `max_ms` points at an unloaded shell, not at the code.

## Sources (2026)

- https://raw.githubusercontent.com/samp-incognito/samp-streamer-plugin/master/streamer.inc — exact `Streamer_UpdateEx(playerid, x, y, z, worldid, interiorid, type, compensatedtime, freezeplayer)` signature.
- https://open.mp/docs/scripting/functions/SetPlayerInterior — interior ids and the "set interior before position" order.
- https://open.mp/docs/scripting/resources/limits — 256 interiors, 2,147,483,647 virtual worlds.
