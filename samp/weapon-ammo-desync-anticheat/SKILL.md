---
name: weapon-ammo-desync-anticheat
description: Use when clients claim weapons or ammo they do not own.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, anticheat, weapons]
    category: samp
---

# Weapon and ammo desync: count shots, not client claims

## When to Use

- A player fires a weapon that was never given to them, or keeps firing with an empty magazine.
- Ammo is restored client-side between shots (reload hack) or jumps without a pickup.
- One player lands more hits per second than the weapon can physically fire.
- You need ban evidence for an infinite-ammo report instead of "an admin saw it".

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.4.x 2026 builds | 13 weapon slots, `GetPlayerWeaponData` covers 0-12 |
| SA-MP server | 0.3.7-R5, 0.3.DL-R1 | identical slot model, no `GetPlayerDialogID` |
| Pawn.RakNet | `omp` branch, 1.6.x | packet `204` (WeaponsUpdate) exposes the client's claim |
| YSI | y_iterate 5.x, y_timers 5.x | optional, keeps the per-second loop cheap |
| pawncc | 3.10.11 or newer | `-d3`; a 217 warning here usually hides a bad tag |

## Production Implementation

1. Split ownership from display. The server decides which weapon a slot holds and how much ammo it has; `GetPlayerAmmo`, `GetPlayerWeaponData` and the HUD are downstream views. Keep a mirror (`invWeapon[13]`, `invAmmo[13]`, `invLastShot`, `invShotCount`, `invDrift`) and grant weapons only through one function that updates it, so drift is measurable and never silent.

2. Judge every shot in `OnPlayerWeaponShot`. The callback only fires for firearms, only with lag compensation enabled, and never for driver drive-by, so a missing call is "no data", not innocence or guilt. Weapon cycle times are config, not guesses:

```pawn
enum E_Inv { invWeapon[13], invAmmo[13], invLastShot, invShotCount, invDrift };
new g_Inv[MAX_PLAYERS][E_Inv];
new g_MinShotMs[47];        // ms per shot, per weapon id, from ac/weapon_limits.ini

#define SHOT_SLACK_MS 35        // ms per shot, per weapon id, from ac/weapon_limits.ini

stock LoadWeaponLimits()
{
    new File:f = fopen("ac/weapon_limits.ini", io_read), line[64], weaponid, ms;
    if (!f) return 0;
    while (fread(f, line))
        if (!sscanf(line, "p<=>d", weaponid, ms) && weaponid >= 0 && weaponid <= 46 && ms > 0)
            g_MinShotMs[weaponid] = ms;
    fclose(f);
    return 1;
}

public OnPlayerWeaponShot(playerid, WEAPON:weaponid, BULLET_HIT_TYPE:hittype, hitid, Float:fX, Float:fY, Float:fZ)
{
    new slot = GetWeaponSlotFor(_:weaponid);
    if (slot < 0) return 0;                                   // not a firearm we track
    if (g_Inv[playerid][invWeapon][slot] != _:weaponid)       // weapon never granted
        return LogAndDrop(playerid, weaponid, "weapon_not_owned");

    new now = GetTickCount(), interval = now - g_Inv[playerid][invLastShot];
    new budget = g_MinShotMs[_:weaponid] - GetPlayerPing(playerid) - SHOT_SLACK_MS;
    if (g_Inv[playerid][invLastShot] != 0 && interval < budget)
        return LogAndDrop(playerid, weaponid, "fire_rate");

    if (g_Inv[playerid][invAmmo][slot] <= 0)                  // server-side count
        return LogAndDrop(playerid, weaponid, "ammo_exhausted");

    g_Inv[playerid][invAmmo][slot]--;
    g_Inv[playerid][invLastShot] = now;
    g_Inv[playerid][invShotCount]++;
    return 1;
}
```

3. Turn one mismatch into a bounded correction, never an instant ban. Define `LogAndDrop` above its first use, or put the stocks in an include:

```pawn
stock LogAndDrop(playerid, weaponid, const reason[])
{
    new slot = GetWeaponSlotFor(_:weaponid);
    SetPlayerAmmo(playerid, weaponid, g_Inv[playerid][invAmmo][slot]);   // server wins
    g_Inv[playerid][invDrift]++;
    LogAmmoEvent(playerid, slot, weaponid, g_Inv[playerid][invAmmo][slot], reason);

    if (g_Inv[playerid][invDrift] >= 3 && g_Inv[playerid][invDrift] < 6)
        BanEx(playerid, "ammo desync, repeated");               // evidence stays on record
    return 0;                                                    // block the shot
}
```

4. Read the client's own claim from packet `204`: packet id, target id, target actor id, then 13 repeats of slot id, weapon id, ammo. An inflated magazine is visible without guessing:

```pawn
const WEAPONS_UPDATE = 204;

IPacket:WEAPONS_UPDATE(playerid, BitStream:bs)
{
    new target, targetActor, slot, weapon, ammo;
    BS_ReadValue(bs, PR_IGNORE_BITS, 8, PR_UINT16, target, PR_UINT16, targetActor);

    for (new i = 0; i <= 12; i++)
    {
        BS_ReadValue(bs, PR_UINT8, slot, PR_UINT8, weapon, PR_UINT16, ammo);
        if (slot > 12) return 0;
        if (ammo > g_Inv[playerid][invAmmo][slot] + 1)     // +1 for the in-flight shot
            return LogAmmoEvent(playerid, slot, weapon, ammo, "ammo_claim");
    }
    return 1;
}
```

5. Keep the evidence line greppable for a year and retain it 30 days (`find scriptfiles/ac -name 'ammo.log*' -mtime +30 -delete`):

```pawn
stock LogAmmoEvent(playerid, slot, weapon, ammo, const reason[])
{
    new File:f = fopen("ac/ammo.log", io_append), line[192], name[MAX_PLAYER_NAME + 1];
    if (!f) return 0;
    GetPlayerName(playerid, name, sizeof name);
    format(line, sizeof line, "AMMO_DESYNC|%d|%d|%d|%d|%d|%d|%s|%s\n", playerid, slot, weapon,
        ammo, g_Inv[playerid][invAmmo][slot], ammo - g_Inv[playerid][invAmmo][slot], reason, name);
    fwrite(f, line);
    fclose(f);
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Legit players flagged on high ping | interval compared without latency | subtract `GetPlayerPing` and `SHOT_SLACK_MS` from the budget |
| Shotgun and sniper shots dropped | one-shot-per-click weapons skip the interval check | exempt weapons whose cycle time exceeds the sample window |
| Ammo drifts upward after a respawn | mirror not reset in `OnPlayerSpawn` | zero the mirror and re-grant through the tracked grant function |
| False "weapon_not_owned" on pickups | weapon added by the pickup system, not the command | snapshot in `OnPlayerPickUpPickup` before judging |
| Every mobile client is flagged | mobile sends no `204` packet | skip the packet gate when `GetPlayerVersion` is a mobile build |

## Verification

```bash
./pawncc gamemodes/main.pwn -d3 -o gamemodes/main.amx
python3 - <<'PY'
import collections
rows = [l.strip().split("|") for l in open("scriptfiles/ac/ammo.log") if l.startswith("AMMO_DESYNC")]
peak = {}
for tag, pid, slot, weapon, claimed, expected, delta, reason, name in rows:
    peak[int(pid)] = max(peak.get(int(pid), 0), int(delta))
print("desync_events", len(rows))
for pid in sorted(peak): print(f"player {pid} max_delta {peak[pid]}")
print("ban_candidates", sum(1 for d in peak.values() if d > 500))
PY
```

```text
desync_events 4
player 7 max_delta 9909
player 9 max_delta 765
player 14 max_delta 0
ban_candidates 2
```

- Manual: grant 100 rounds and hold fire; server count and HUD stay within one round, and no line is written; a rapid-fire client is dropped on the first impossible interval.

## Sources (2026)

- https://open.mp/docs/scripting/callbacks/OnPlayerWeaponShot — firearms only, lag compensation required, drive-by gaps.
- https://open.mp/docs/scripting/functions/GetPlayerWeaponData — slots 0-12, empty weapons still returned.
- https://github.com/katursis/Pawn.RakNet/wiki/WeaponsUpdate — packet 204 field order and 13 slot repeats.
