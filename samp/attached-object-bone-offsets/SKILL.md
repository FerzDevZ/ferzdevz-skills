---
name: attached-object-bone-offsets
description: Use when attached objects float, detach or miss a slot.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping, attachments]
    category: samp
---

# Attach objects by documented bone id and fixed slot

Attached objects live in a 10-slot pool per player, separate from `CreateObject`. The bone id
anchors the object and offsets are in that bone's space: a hat on bone 1 hangs off the spine.

## When to Use

- A hat, bag or holster sits in the chest, at the feet, or behind the head.
- The object disappears after a skin change, a respawn or an animation.
- The eleventh attachment silently does nothing.

## Compatibility & Stack Matrix (2026)

| Item | open.mp 1.6.x | SA-MP 0.3.7-R2 |
| --- | --- | --- |
| Slots per player | 10, indexes 0-9 | same |
| Bone ids | 1-18, documented table | same table |
| Clear one slot | `RemovePlayerAttachedObject` | same |
| Occupancy test | `IsPlayerAttachedObjectSlotUsed` | same |
| Material colours | `materialColour1/2` params exist | not available |
| Vehicle props | `AttachObjectToVehicle`, object pool | same |

The bone table is fixed: 1 spine, 2 head, 3 left upper arm, 4 right upper arm, 5 left hand,
6 right hand, 7 left thigh, 8 right thigh, 9 left foot, 10 right foot, 11 right calf, 12 left
calf, 13 left forearm, 14 right forearm, 15 left clavicle, 16 right clavicle, 17 neck, 18 jaw.

## Production Implementation

1. Encode that table once, in order, so a later edit cannot shift every id by one. The last
   member is checked against 18 at boot instead of guessed.

```pawn
enum E_BONE
{
    BONE_SPINE = 1, BONE_HEAD, BONE_L_UPPER_ARM, BONE_R_UPPER_ARM,
    BONE_L_HAND, BONE_R_HAND, BONE_L_THIGH, BONE_R_THIGH,
    BONE_L_FOOT, BONE_R_FOOT, BONE_R_CALF, BONE_L_CALF,
    BONE_L_FOREARM, BONE_R_FOREARM, BONE_L_CLAVICLE, BONE_R_CLAVICLE,
    BONE_NECK, BONE_JAW
};

stock Bone_CheckTable()
{
    if (_:BONE_JAW != 18) printf("BONE drift last=%d", _:BONE_JAW);
}
```

2. Assign slots per feature instead of taking "the next free one". Two systems that both pick
   slot 3 overwrite each other without a log line.

```pawn
#define SLOT_COUNT (3)
enum { SLOT_HAT = 0, SLOT_BAG, SLOT_HOLSTER };

#if SLOT_COUNT > 10
    #error attached objects exceed the 10-slot pool
#endif
```

3. Describe each attachment as data and apply it in one loop. Removing first makes the return
   value meaningful: a failed set leaves the slot empty instead of stale.

```pawn
enum E_ATTACH
{
    E_MODEL, E_BONE, Float:E_OX, Float:E_OY, Float:E_OZ,
    Float:E_RX, Float:E_RY, Float:E_RZ, Float:E_SX, Float:E_SY, Float:E_SZ
};

new const g_Attach[][E_ATTACH] =
{
    { 19142, BONE_SPINE, 0.10, 0.02, 0.00, 0.0, 0.0, 90.0, 1.0, 1.0, 1.0 },
    { 18634, BONE_HEAD,  0.00, 0.00, 0.00, 0.0, 0.0, 0.0,  1.0, 1.0, 1.0 }
};

stock Attach_Apply(playerid)
{
    for (new slot = 0; slot < sizeof g_Attach; slot++)
    {
        if (IsPlayerAttachedObjectSlotUsed(playerid, slot)) RemovePlayerAttachedObject(playerid, slot);
        if (!SetPlayerAttachedObject(playerid, slot, g_Attach[slot][E_MODEL], g_Attach[slot][E_BONE],
                g_Attach[slot][E_OX], g_Attach[slot][E_OY], g_Attach[slot][E_OZ],
                g_Attach[slot][E_RX], g_Attach[slot][E_RY], g_Attach[slot][E_RZ],
                g_Attach[slot][E_SX], g_Attach[slot][E_SY], g_Attach[slot][E_SZ]))
            printf("ATTACH fail player=%d slot=%d model=%d", playerid, slot, g_Attach[slot][E_MODEL]);
    }
    return 1;
}
```

4. Call `Bone_CheckTable()` once in `OnGameModeInit`, then re-run `Attach_Apply` on every path
   that changes the skeleton: spawn, class selection, admin skin change. `SetPlayerSkin` clears
   the slots, so the rebuild sits after it.

5. Measure offsets in game with `EditAttachedObject`, then paste them into `g_Attach`. Rotation
   is applied in degrees before scale, so a guessed 90 degree turn misses the frame.

6. Treat vehicle props as a separate system: `AttachObjectToVehicle` uses an object-pool id and
   model-space offsets, and the object is not destroyed with the car. It stays where the car died
   and reattaches to whatever takes that id next.

```pawn
new g_PropObj[MAX_VEHICLES + 1] = { INVALID_OBJECT_ID, ... };

public OnVehicleDeath(vehid, killerid)
{
    if (g_PropObj[vehid] != INVALID_OBJECT_ID)
    {
        DestroyObject(g_PropObj[vehid]);
        g_PropObj[vehid] = INVALID_OBJECT_ID;
    }
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Object hangs off the chest | bone 1 (spine) used for a hat | use `BONE_HEAD`, 2 |
| Object sinks into the body | offsets measured on a taller skin | re-measure with `EditAttachedObject`, add scale |
| Attachment gone after a skin change | `SetPlayerSkin` clears the slots | re-run `Attach_Apply` after the skin is set |
| 11th object never appears | slot index beyond 9 | fixed slot enum plus the compile guard |
| Object invisible | scale left at 0 | set `E_SX/E_SY/E_SZ` to 1.0 |
| Prop floats where a car died | attached object outlives the vehicle | destroy in `OnVehicleDeath` and on respawn |

## Verification

The table exists in two places (the enum and the boot check) and the check stays silent:

```bash
grep -c 'BONE_JAW' gamemodes/attachments.pwn
grep 'BONE drift' log.txt | wc -l
```

```text
2
0
```

Slot count after a respawn and again after a skin change:

```pawn
new count;
for (new slot = 0; slot < 10; slot++) if (IsPlayerAttachedObjectSlotUsed(playerid, slot)) count++;
printf("ATTACH player=%d slots=%d", playerid, count);
```

```text
ATTACH player=7 slots=2
```

Two attachments before and after the skin change is the proof; zero means the rebuild is missing.

## Sources (2026)

- https://open.mp/docs/scripting/functions/SetPlayerAttachedObject
- https://open.mp/docs/scripting/resources/boneid
- https://open.mp/docs/scripting/functions/AttachObjectToVehicle
