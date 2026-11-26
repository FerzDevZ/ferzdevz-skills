---
name: exterior-world-lod-drawdistance
description: Use when exteriors flicker or vanish at distance.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping, streamer, lod]
    category: samp
---

# LODs and draw distance that hold past 299 units

The client renders normal objects out to 299 units; only LOD-class geometry is
drawn in the 300-3000 band, which is why a hand-built skyline disappears the
moment you step back. A working exterior has two objects per landmark - a full
mesh that stops at 298 and a low-detail shell that takes over from 298 to its own
draw distance - plus a stream distance above both so the streamer never removes
the pair before the transition happens.

## When to Use

- A custom map's buildings vanish or pop in when a player walks away.
- The LOD shell and the full model fight at the same distance (z-fighting flicker).
- Landmarks are invisible from a neighbouring district but fine up close.
- Exterior LODs bleed into interiors because they were created in world 0.
- You need to explain why `drawdistance 3000` did nothing for a streamed object.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | `CreateObject` takes `Float:drawDistance`, `0.0` = game default |
| Draw range | normal objects to 299 units | `CreateObject` example raises a landmark to `300.0` |
| LOD band | 300-3000 units in map IDE data | anything above the band is never rendered by the client |
| Streamer | Incognito Streamer 2.9.6 | `STREAMER_OBJECT_SD` = 300.0, `STREAMER_OBJECT_DD` = 0.0 by default |
| Handover | `drawdistance` < `streamdistance` | an object removed at SD never gets to use its DD |
| Isolation | `worldid` / `interiorid` on every LOD | a LOD in world 0 shows through interior walls |
| Introspection | `GetObjectDrawDistance`, `Streamer_GetFloatData` | read the value back instead of trusting the source |

## Production Implementation

1. Pick a tier per object type and write it down. Uniform distances are what
   produce both pop-in and 4000 visible objects per player.

| Tier | Stream distance | Draw distance | Example |
| --- | --- | --- | --- |
| Prop | 120.0 | 100.0 | bins, signs, interior clutter |
| Building | 320.0 | 298.0 | full mesh of a landmark |
| LOD shell | 420.0 | 340.0 | low-poly twin of that landmark |
| Backdrop | not streamed | static map | the GTA map itself, never duplicated |

2. Create the pair with explicit numbers. The LOD's stream distance must exceed
   both draw distances, otherwise the streamer frees it at 300 while the client
   is still inside its draw band.

```pawn
#define DD_FULL   298.0
#define DD_LOD    340.0
#define SD_PAIR   420.0

stock LandmarkPair(fullmodel, lodmodel, Float:x, Float:y, Float:z, Float:rz,
                   world, interior)
{
    // Full mesh: disappears at 298, where the shell takes over.
    CreateDynamicObject(fullmodel, x, y, z,        0.0, 0.0, rz,
                        world, interior, -1, SD_PAIR, DD_FULL);
    // Shell: same pivot, sunk 0.20 so the full mesh wins the z-test up close.
    CreateDynamicObject(lodmodel,  x, y, z - 0.20, 0.0, 0.0, rz,
                        world, interior, -1, SD_PAIR, DD_LOD);
}
```

3. Keep the shell's pivot and footprint identical to the full model. A shell
   that is scaled or offset in X/Y shows a visible jump at the handover; only
   the Z sink is intentional.

4. Make the shell collision-free. If the LOD model carries collision, players
   walk on geometry they cannot see at range and fall through it at 299. Use a
   collision-less model, or keep the shell 1.0 unit below the play surface.

5. Create LODs in the same virtual world and interior as the full model. An
   interior shell left in world 0 is visible through the interior walls from
   outside, which looks like a building floating in the street.

```pawn
// Interior shell: world 0, interior 3, exactly like the room it belongs to
CreateDynamicObject(lodmodel, x, y, z - 0.20, 0.0, 0.0, rz,
                    0, 3, -1, SD_PAIR, DD_LOD);
```

6. Do not raise `drawdistance` above the next tier to "fix" pop-in. A streamed
   object beyond 300 units is drawn only if the client treats it as LOD
   geometry; raising the number on a normal model changes nothing and hides the
   real problem (missing shell).

7. Measure instead of guessing. Read the draw distance back per object and count
   what each player can see.

```pawn
CMD:lodstat(playerid, params[])
{
    new obj = strval(params), Float:dd, Float:sd;
    Streamer_GetFloatData(STREAMER_TYPE_OBJECT, obj, E_STREAMER_DRAW_DISTANCE, dd);
    Streamer_GetFloatData(STREAMER_TYPE_OBJECT, obj, E_STREAMER_STREAM_DISTANCE, sd);
    new msg[144];
    format(msg, sizeof msg, "obj %d dd %.1f sd %.1f visible %d", obj, dd, sd,
           Streamer_CountVisibleItems(playerid, STREAMER_TYPE_OBJECT, 1));
    SendClientMessage(playerid, -1, msg);
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Building pops out at exactly 300 units | only a full mesh was created | add a shell with DO 340 and SD 420 |
| Shell flickers against the full mesh | both render in 298-340 with the same pivot height | sink the shell 0.15-0.30 and stop the full mesh at 298 |
| Landmark visible up close, gone at range | `drawdistance` set but `streamdistance` left at the 300 default | set SD above DD on every streamed object |
| `drawdistance 3000` changes nothing | normal objects are not LOD geometry | keep the shell in the 300-340 band, do not chase 3000 |
| Exterior shell seen inside an interior | LOD created in world 0 / interior 0 | pass the room's world and interior to every LOD call |
| Players fall through an invisible floor at range | shell model carries collision | use a collision-less shell or sink it 1.0 unit |

## Verification

```bash
grep -rn "CreateDynamicObject" gamemodes/ | grep -v "SD_PAIR" | head
pawncc -i includes gamemodes/main.pwn -o /tmp/main.amx
```

- Every landmark call site uses the named `SD_PAIR` / `DD_*` constants, so no
  object keeps the 300.0 stream default by accident.
- `pawncc` finishes with no warnings on the LOD stock.
- In game, `/lodstat <obj>` shows `dd 298.0 sd 420.0` for the full mesh and
  `dd 340.0 sd 420.0` for the shell, and walking 250 -> 400 units away swaps one
  for the other with no frame where both are drawn.

## Sources (2026)

- https://open.mp/docs/scripting/functions/CreateObject
- https://web.archive.org/web/2024/https://gtamods.com/wiki/Draw_distance
- https://github.com/samp-incognito/samp-streamer-plugin/wiki/Natives-(Objects)
