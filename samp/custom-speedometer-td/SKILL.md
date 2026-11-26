---
name: custom-speedometer-td
description: Use when a speedometer reads the wrong km/h.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, vehicles]
    category: samp
---

# Draw a speedometer that matches the road

`GetVehicleVelocity` returns the game's internal velocity, not metres per second: it is metres per
20 ms tick, so a car at 200 km/h reads about 1.11. The 180.0 factor is derived, not tuned — 50 ticks
per second x 3.6 = 180 — and getting it wrong skews every number on the HUD by the same ratio.

## When to Use

- The HUD says 160 km/h while traffic is passing you on a 200 km/h road.
- Digits flicker, or CPU grows with player count because the draw is set every frame.
- The panel stays on screen after leaving the vehicle, or a second timer starts on re-entry.

## Compatibility & Stack Matrix (2026)

| Item | 0.3.7-R2 | open.mp 1.6.x | Rule |
| --- | --- | --- | --- |
| `GetVehicleVelocity` units | metres per 20 ms tick | identical | never treat the result as m/s |
| km/h factor | 180.0 | 180.0 | `magnitude * 50 * 3.6`, derived, not tuned |
| Handle type | `PlayerText:` | `PlayerText:` | one draw per player, 256 cap |
| `PlayerTextDrawSetString` | needs `format()` first | variadic, args inline | do not copy 0.3.7 formatting into open.mp |
| Centre alignment constant | `TEXT_DRAW_ALIGN_CENTER` | `TEXT_DRAW_ALIGN_CENTRE` (alias kept) | either compiles on open.mp |

180.0 is derived: 50 ticks/s x 3.6. 195.0 (mobile snippets) reads 8.3% high, so a 200 km/h car shows
217; `136.666` from old HUD includes reads 24% low. A calibration gap over 2% means the measurement
is wrong — a slope, a corner, or `vz` folded into the magnitude.

## Production Implementation

1. Convert in one place, and use the horizontal magnitude only. Including `vz` makes the number jump
   every time a wheel leaves the ground:

```pawn
#define SPEED_KMH 180.0        // 50 ticks/s * 3.6, exact

stock Float:VehicleSpeedKmh(vehicleid)
{
    new Float:vx, Float:vy, Float:vz;
    if (!GetVehicleVelocity(vehicleid, vx, vy, vz)) return 0.0;
    return floatsqroot(vx * vx + vy * vy) * SPEED_KMH;
}
```

2. Keep one draw and one timer per player. Re-entering a vehicle must reuse the draw and replace the
   timer, never add to it:

```pawn
new PlayerText:g_SpeedTD[MAX_PLAYERS] = {INVALID_PLAYER_TEXT_DRAW, ...};
new g_SpeedTimer[MAX_PLAYERS];
new g_SpeedShown[MAX_PLAYERS] = {-1, ...};

stock SpeedTD_Build(playerid)
{
    g_SpeedTD[playerid] = CreatePlayerTextDraw(playerid, 300.0, 380.0, "0 km/h");
    PlayerTextDrawLetterSize(playerid, g_SpeedTD[playerid], 0.32, 1.4);
    PlayerTextDrawAlignment(playerid, g_SpeedTD[playerid], TEXT_DRAW_ALIGN_CENTRE);
    PlayerTextDrawColour(playerid, g_SpeedTD[playerid], 0xFFFFFFFF);
    PlayerTextDrawUseBox(playerid, g_SpeedTD[playerid], true);
    PlayerTextDrawBoxColour(playerid, g_SpeedTD[playerid], 0x000000AA);
    PlayerTextDrawTextSize(playerid, g_SpeedTD[playerid], 56.0, 18.0);
    return 1;
}
```

3. Start on the driver seat and stop on the way out. `OnPlayerStateChange` is the only place that
   knows both edges, so the lifecycle lives there:

```pawn
public OnPlayerStateChange(playerid, PLAYER_STATE:newstate, PLAYER_STATE:oldstate)
{
    if (newstate == PLAYER_STATE_DRIVER)
    {
        if (g_SpeedTD[playerid] == INVALID_PLAYER_TEXT_DRAW) SpeedTD_Build(playerid);
        if (g_SpeedTimer[playerid]) KillTimer(g_SpeedTimer[playerid]);   // re-entry never stacks
        g_SpeedTimer[playerid] = SetTimerEx("SpeedTD_Tick", 100, true, "i", playerid);
    }
    else if (oldstate == PLAYER_STATE_DRIVER) SpeedTD_Stop(playerid);
    return 1;
}
```

4. Redraw only when the integer changes. Ten updates a second that write the same string are pure
   cost, and they are what makes the digits shimmer:

```pawn
stock SpeedTD_Stop(playerid)
{
    if (g_SpeedTimer[playerid]) { KillTimer(g_SpeedTimer[playerid]); g_SpeedTimer[playerid] = 0; }
    if (g_SpeedTD[playerid] != INVALID_PLAYER_TEXT_DRAW) PlayerTextDrawHide(playerid, g_SpeedTD[playerid]);
    g_SpeedShown[playerid] = -1;
    return 1;
}

forward SpeedTD_Tick(playerid);
public SpeedTD_Tick(playerid)
{
    if (GetPlayerState(playerid) != PLAYER_STATE_DRIVER) return SpeedTD_Stop(playerid);
    new kmh = floatround(VehicleSpeedKmh(GetPlayerVehicleID(playerid)));
    if (kmh > 400) {                            // teleport, tow or desync spike
        g_SpeedShown[playerid] = -1; PlayerTextDrawSetString(playerid, g_SpeedTD[playerid], "---");
        return 1;
    }
    if (kmh == g_SpeedShown[playerid]) return 1;
    g_SpeedShown[playerid] = kmh;
    PlayerTextDrawSetString(playerid, g_SpeedTD[playerid], "%d km/h", kmh);
    return 1;
}
```

5. Expose a calibration command that prints the raw magnitude and both factors:

```pawn
CMD:spdcal(playerid, params[])
{
    #pragma unused params
    new Float:vx, Float:vy, Float:vz, Float:mag;
    if (!IsPlayerInAnyVehicle(playerid)) return SendClientMessage(playerid, -1, "SPDCAL: not in a vehicle");
    GetVehicleVelocity(GetPlayerVehicleID(playerid), vx, vy, vz);
    mag = floatsqroot(vx * vx + vy * vy);
    printf("SPDCAL p=%d v=%.3f kmh=%.0f alt195=%.0f", playerid, mag, mag * 180.0, mag * 195.0);
    return 1;
}
```

6. Tie cleanup to the session, because a disconnected player frees the slots while your handles stay
   stale:

```pawn
public OnPlayerDisconnect(playerid, reason)
{
    SpeedTD_Stop(playerid);
    if (g_SpeedTD[playerid] != INVALID_PLAYER_TEXT_DRAW) PlayerTextDrawDestroy(playerid, g_SpeedTD[playerid]);
    g_SpeedTD[playerid] = INVALID_PLAYER_TEXT_DRAW; return 1;
}
```
## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Reading is 8.3% high at every speed | 195.0 copied from a mobile snippet | 180.0, then re-run `/spdcal` on a flat straight |
| Reading is 24% low | `136.666` from an old HUD include | 180.0, and delete the old helper |
| Digits shimmer, CPU grows per player | `PlayerTextDrawSetString` in `OnPlayerUpdate` | 100 ms timer, write only when the integer changes |
| Two speeds flash alternately | a second timer left alive after re-entry | `KillTimer` before every `SetTimerEx` |
| HUD stays after exiting the car | only the entering edge handled | stop on `oldstate == PLAYER_STATE_DRIVER` |

## Verification

```bash
pawncc gamemodes/speedo.pwn -i"$HOME/samp-sdk/omp-stdlib" -o/tmp/speedo.amx
```

Expected: `Done.` with no `Error:` or `Warning:` lines. Stopped, the HUD reads `0 km/h`; a measured
1 km flat run must match `1000 m / seconds * 3.6`. `/spdcal` at 200 km/h prints `v` near `1.11` with
`kmh=200` and `alt195=217`, so a HUD tracking `alt195` has the wrong constant compiled.

## Sources (2026)

- https://open.mp/docs/scripting/functions/GetVehicleVelocity
- https://open.mp/docs/scripting/functions/PlayerTextDrawSetString
- https://open.mp/docs/scripting/functions/SetTimerEx
