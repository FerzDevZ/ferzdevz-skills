---
name: custom-interior-shell-builder
description: Use when a custom interior leaks into the street.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping, streamer, interiors]
    category: samp
---

# A shell is a closed object box in its own world, not a room in world 0

Custom interiors fail in three ways: geometry from the shell is visible from the
street because it shares world 0, the player walks through a wall because the
model has no collision, or the room is fine but the radar still shows Los Santos
because the interior id was never set. Build the shell outside the map bounds,
give it a private virtual world, verify collision by walking the perimeter, and
route the door with an explicit teleport that sets world and interior before it
moves the player.

## When to Use

- A mapped interior (MTA, Texture Studio, hand-placed objects) shows flickering
  walls from the street or from a neighbouring interior.
- Players fall through the floor at the doorway or clip through a wall corner.
- Two players in different "rooms" see and shoot each other.
- Radar, weapon rules or radio behave like the street while inside the room.
- Not for routing existing GTA interiors — that is `interior-virtualworld-routing`.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.6.x | `SetPlayerVirtualWorld`, `SetPlayerInterior`, `SetPlayerPos` |
| SA-MP server | 0.3.7-R5 / 0.3.DL-R1 | same three natives, no components |
| Streamer | 2.9.6 | `CreateDynamicObject(modelid, x, y, z, rx, ry, rz, worldid, interiorid, ...)` |
| Streamer interior arg | `interiorid = -1` | `-1` makes the object visible from every interior id |
| Collision (standard models) | client-side COL | comes with the model; no plugin needed |
| Collision (custom DFF) | ColAndreas / baked COL | a custom model without COL has no collision at all |
| Shell origin | outside `±3000` | the SA map ends near those bounds; nothing streams there |

## Production Implementation

1. Allocate one virtual world per interior instance, and a stable interior id for
   the radar and interior rules. The virtual world is what hides the geometry;
   the interior id does not hide anything.

```pawn
#define MAX_SHELLS       64
#define SHELL_BASE_WORLD 1000            // world 1000..1063, never world 0
#define SHELL_INTERIOR   3               // radar/audio/weapon rules inside
#define SHELL_ORIGIN_X   3500.0          // outside the SA map: no street geometry
#define SHELL_ORIGIN_Y   3500.0

new g_ShellWorld[MAX_SHELLS];
new g_ShellObjects[MAX_SHELLS][96];
new g_ShellCount[MAX_SHELLS];
```

2. Spawn the shell with both the world and the interior on every object. Passing
   `-1` for `interiorid` is the usual leak: the object then appears in every
   interior of that world, including the street if a player is ever in world 1000.

```pawn
stock LoadShell(shellid, const Float:offX, const Float:offY)
{
    new Float:x = SHELL_ORIGIN_X + offX, Float:y = SHELL_ORIGIN_Y + offY;
    g_ShellWorld[shellid] = SHELL_BASE_WORLD + shellid;
    g_ShellCount[shellid] = 0;

    // floor 16x16, four walls, ceiling: a closed box, no gaps at the corners
    g_ShellObjects[shellid][g_ShellCount[shellid]++] = CreateDynamicObject(19450,
        x, y, -1.0, 0.0, 0.0, 0.0, g_ShellWorld[shellid], SHELL_INTERIOR, -1, 200.0, 200.0);
    g_ShellObjects[shellid][g_ShellCount[shellid]++] = CreateDynamicObject(19450,
        x, y, 4.0, 0.0, 90.0, 0.0, g_ShellWorld[shellid], SHELL_INTERIOR, -1, 200.0, 200.0);
    return 1;
}
```

3. Test the perimeter before decorating. A shell that looks closed from the spawn
   point can have a one-unit gap at a corner; walk a full lap in first person and
   push into every wall. Collision comes from the model's COL, not from the
   object's size — a `19450` plane has collision, a `19473` ramp edge may not.

4. For custom DFF models, add server-side collision explicitly. The client has no
   COL for a model shipped without one, so streamer objects alone let players walk
   through the wall. Register the same transform with ColAndreas:

```pawn
new ca = CA_CreateObject(modelid, x, y, z, rx, ry, rz, true);
if (ca == -1) printf("[shell] no collision for model %d", modelid);
```

5. Route the door with a teleport that sets world and interior before the
   position, then force a streamer refresh so the room is not empty for one tick.

```pawn
stock EnterShell(playerid, shellid)
{
    SetPlayerVirtualWorld(playerid, g_ShellWorld[shellid]);
    SetPlayerInterior(playerid, SHELL_INTERIOR);
    SetPlayerPos(playerid, SHELL_ORIGIN_X + 0.0, SHELL_ORIGIN_Y + 0.0, 1.0);
    SetCameraBehindPlayer(playerid);
    Streamer_Update(playerid);          // 2.9.6: refresh now, not on the next tick
    return 1;
}

stock ExitShell(playerid)
{
    SetPlayerVirtualWorld(playerid, 0);
    SetPlayerInterior(playerid, 0);
    SetPlayerPos(playerid, g_DoorX, g_DoorY, g_DoorZ);
    Streamer_Update(playerid);
    return 1;
}
```

6. Put a solid facade on both sides of the door. Without it the player stands in
   the street inside the wall texture, or exits into a doorway they can walk back
   through without the gate check running.

7. Budget the shell: 96 objects per shell times 64 shells is 6144 streamer items.
   Streamer handles it, but each shell must be destroyed or never loaded when
   empty. Track `g_ShellCount` and destroy on unload to keep
   `Streamer_CountItems(STREAMER_TYPE_OBJECT)` flat.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Shell walls flicker from the street | object created with `worldid = -1` or the shell sits inside the SA map | explicit world id, origin beyond `±3000` |
| Player walks through a wall | model has no collision, or the gap is between two objects | test `CA_RayCastLine` through the wall; add a COL/ColAndreas object |
| Player falls through the floor on entry | floor object missing or spawned after the teleport | create the shell at startup, teleport after, call `Streamer_Update` |
| Two groups in different rooms see each other | both shells share one virtual world | one world per shell instance, `SHELL_BASE_WORLD + shellid` |
| Radar shows the street inside the room | `SetPlayerInterior` never called or called after `SetPlayerPos` | set interior and world before moving the player |
| Interior still empty for a moment after entry | streamer only pushes new items on its next tick | `Streamer_Update(playerid)` after the teleport |
| Object count grows every entry | shell re-created per player without destroy | create once per shell, destroy on unload, count it |

## Verification

```bash
# compile the shell module, then count shell objects on a live server console
pawncc -i include -d3 shell.pwn -o shell.amx
rcon "shellinfo"
```

```pawn
// /shellinfo handler: proves the player is in the shell world and the box loaded
new str[128];
format(str, sizeof str, "world=%d interior=%d objects=%d shell=%d",
    GetPlayerVirtualWorld(playerid), GetPlayerInterior(playerid),
    g_ShellCount[g_PlayerShell[playerid]], g_PlayerShell[playerid]);
SendClientMessage(playerid, -1, str);
```

- Compile prints no errors and no warnings about tag mismatch on `worldid`.
- In game `/shellinfo` reports `world=1000 interior=3 objects=96 shell=0` — a
  `world=0` means the teleport order is wrong, and `objects=0` means the load is
  running per player instead of per shell.
- Console `Streamer_CountItems(STREAMER_TYPE_OBJECT)` returns 96 per loaded shell
  and drops back by 96 after the shell unloads, so nothing leaks.

## Sources (2026)

- https://open.mp/docs/scripting/functions/SetPlayerVirtualWorld
- https://open.mp/docs/scripting/resources/interiorids
- https://raw.githubusercontent.com/samp-incognito/samp-streamer-plugin/master/streamer.inc
