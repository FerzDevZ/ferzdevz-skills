---
name: custom-weapon-damage-config
description: Use when stock weapon damage breaks your combat balance.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, combat, damage, balance]
    category: samp
---

# Own the damage number: server table, shadow health, absolute writes

`OnPlayerTakeDamage` hands you `amount`: the maximum the weapon can do, health and armour
combined, not what the victim lost - and the engine already wrote its own result before the
callback runs. A config that subtracts `amount * multiplier` from current health therefore
double-counts or kills through armour. Keep an authoritative health value, compute the hit
from a table, write the absolute result.

## When to Use

- Damage values must differ from stock (hardcore, roleplay, arena balance).
- Headshots and armour interact in a way the table does not explain.
- A weapon nobody configured one-shots players.
- You need evidence for "this player hits too hard" reports.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 / SA-MP 0.3.7-R2 | same callbacks, 100.0 health ceiling |
| `OnPlayerTakeDamage` | `playerid, issuerid, Float:amount, WEAPON:weaponid, bodypart` | fires after engine damage |
| `amount` semantics | weapon maximum, health + armour combined | not the applied delta |
| Fire / explosion ids | 37 for any fire source, 51 for any explosion | the real weapon id is lost |
| Body parts | 3 torso, 4 groin, 5/6 arms, 7/8 legs, 9 head | not declared in any include |
| `OnPlayerWeaponShot` | return 0 cancels bullet damage | firearms, lag compensation only |
| `SetPlayerHealth` | 0.0 triggers death | absolute write, never a delta |

## Production Implementation

1. One table, one file, loaded once. Zero means "not configured" and keeps engine damage,
   which is safer than an accidental zero multiplier:

```pawn
#include <openmp>

#define MAX_DAMAGE_WEAPONS (47)
#define BODY_PART_HEAD (9)
#define ARMOUR_ABSORB (0.5)

new Float:gDmg[MAX_DAMAGE_WEAPONS], Float:gHead[MAX_DAMAGE_WEAPONS];
new Float:gHealth[MAX_PLAYERS], Float:gArmour[MAX_PLAYERS];

stock DamageLoad(const file[])
{
    for (new w = 0; w < MAX_DAMAGE_WEAPONS; w++) { gDmg[w] = 0.0; gHead[w] = 1.0; }
    new File:f = fopen(file, io_read), line[64], w, Float:d, Float:h;
    if (!f) { print("[dmg] table missing, engine damage stays"); return 0; }
    while (fread(f, line))
    {
        if (line[0] == '#' || line[0] == '\0') continue;
        if (sscanf(line, "dff", w, d, h)) continue;
        if (w < 0 || w >= MAX_DAMAGE_WEAPONS || d <= 0.0) continue;
        gDmg[w] = d;
        gHead[w] = (h >= 1.0) ? h : 1.0;
    }
    fclose(f);  printf("[dmg] %s loaded", file);
    return 1;
}
```

2. Keep the shadow copy and make it the only writer, so it cannot drift from the HUD:

```pawn
stock DamageSet(playerid, Float:health, Float:armour)
{
    if (health < 0.0) health = 0.0;  else if (health > 100.0) health = 100.0;
    if (armour < 0.0) armour = 0.0;  else if (armour > 100.0) armour = 100.0;

    gHealth[playerid] = health;  gArmour[playerid] = armour;
    SetPlayerArmour(playerid, armour);
    SetPlayerHealth(playerid, health);
    return 1;
}
```

3. Resolve one hit: table value, head multiplier, armour first, then health, then one
   absolute write. Armour eating a fixed share is what lets an armoured player survive a
   burst that kills an unarmoured one:

```pawn
stock DamageApply(playerid, weaponid, bodypart)
{
    if (weaponid < 0 || weaponid >= MAX_DAMAGE_WEAPONS) return 0;
    if (gDmg[weaponid] <= 0.0) return 0;             // unconfigured: engine value stands

    new Float:dmg = gDmg[weaponid];
    if (bodypart == BODY_PART_HEAD) dmg *= gHead[weaponid];
    new Float:armour = gArmour[playerid];
    if (armour > 0.0)
    {
        new Float:eaten = dmg * ARMOUR_ABSORB;
        if (eaten > armour) eaten = armour;
        armour -= eaten;
        dmg -= eaten;
    }
    return DamageSet(playerid, gHealth[playerid] - dmg, armour);
}
```

4. Hook the callback and skip everything that is not player-versus-player. World damage
   arrives with `issuerid == INVALID_PLAYER_ID`, self-damage with `issuerid == playerid`,
   and both must stay with the engine:

```pawn
public OnPlayerTakeDamage(playerid, issuerid, Float:amount, WEAPON:weaponid, bodypart)
{
    if (issuerid == INVALID_PLAYER_ID || issuerid == playerid) return 1;
    if (GetPlayerState(playerid) == PLAYER_STATE_WASTED) return 1;
    if (gHealth[playerid] <= 0.0) return 1;          // engine kill already landed
    DamageApply(playerid, _:weaponid, bodypart);
    return 1;
}
```

5. Accept the case the correction cannot win: if the engine's own hit is lethal, the player
   is dead when the callback fires and no write revives them. Keep table values at or below
   vanilla, or cancel bullets instead with `OnPlayerWeaponShot` returning 0 after
   `DamageApply(hitid, _:weaponid, 3)` - lag compensation only, and no headshot body part.

6. Every respawn and heal path calls `DamageSet`; a direct `SetPlayerHealth` elsewhere is how
   the shadow drifts. Log three things only: an unconfigured weapon id, a table value above
   100.0, and more than three hits from one attacker inside a tick.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Damage applied twice on rifles | engine write plus a delta from current health | write absolute values from the shadow copy |
| Headshots do nothing | `bodypart` ignored | multiply by `gHead` when `bodypart == 9` |
| Player survives an obviously lethal hit | engine kill short-circuits the correction | keep table values at or below vanilla, or cancel the bullet |
| Healing makes the next hit overshoot | another script called `SetPlayerHealth` directly | route every write through `DamageSet` |
| Melee ignores the table | weapon id missing from `weapon_damage.cfg` | log unknown ids, fall back to engine |
| Armour never drops | only health written | subtract from armour first, then health |
| Damage logged for fall or fire | `issuerid == INVALID_PLAYER_ID` not skipped | return early for world damage |

## Verification

The table is validated before boot, and health may be written from exactly one file:

```bash
awk '/^[0-9]/ { if ($2 <= 0 || $2 > 100) {print "bad damage", $1; bad++} if ($3 < 1 || $3 > 4) {print "bad head mult", $1; bad++} n++ } END { print (bad ? "FAIL" : "table ok"), n, "rows" }' weapon_damage.cfg
grep -rn "SetPlayerHealth" gamemodes/ | grep -v "damage.pwn"; echo "writers_exit=$?"
```

Expected:

```text
table ok 34 rows
writers_exit=1
```

`writers_exit=1` is the pass condition. In game, two hits on an armoured player remove
exactly the table value once armour is gone.

## Sources (2026)

- https://open.mp/docs/scripting/callbacks/OnPlayerTakeDamage — `amount` is the weapon maximum and health+armour combined; 37 for fire, 51 for explosions.
- https://open.mp/docs/scripting/callbacks/OnPlayerWeaponShot — returning 0 cancels bullet damage; only fires with lag compensation enabled.
- https://open.mp/docs/scripting/resources/bodyparts — body part ids, head is 9, and no include declares them.
