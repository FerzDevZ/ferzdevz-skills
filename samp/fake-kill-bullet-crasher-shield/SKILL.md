---
name: fake-kill-bullet-crasher-shield
description: Use when fake kill or bullet crasher packets hit.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, security, anticheat]
    category: samp
---

# Fake kill and bullet crashers: drop the claim, keep the evidence

## When to Use

- A player dies or loses health with no shooter, no muzzle flash and no `OnPlayerWeaponShot`.
- `OnPlayerDeath` fires with `killerid == INVALID_PLAYER_ID` while the victim was alone.
- Clients freeze or crash right after one player fires, or the server log ends at a shot.
- You already log deaths and want to turn that log into a blocking gate.
- Do not use this for legitimate warps: see `teleport-airbreak-detection` instead.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.4.x 2026 builds | incoming RPC 115 is still applied as damage |
| SA-MP server | 0.3.7-R5, 0.3.DL-R1 | same RPC and packet ids, no `GetPlayerDialogID` |
| Pawn.RakNet | `omp` branch, 1.6.x | needed only for the hard RPC/packet gate |
| pawncc | 3.10.11 or newer | compile with `-d3`, never suppress 203/217 |
| Client mix | omp launcher, 0.3.7, mobile | mobile sends fewer bullet syncs; absence is not proof |

## Production Implementation

1. Fix the trust boundary first. Damage arrives as incoming RPC `115` (`GiveTakeDamage`: `bool giveOrTake, UINT16 playerid, float amount, UINT32 weaponid, UINT32 bodypart` in the 2026 RPC list) and the server applies it unchanged. `OnPlayerTakeDamage` then reports `amount` as the weapon's maximum damage, not the health actually removed, and `GetPlayerHealth` inside that callback still returns the pre-damage value. Every number in the callback is a claim, not a measurement.

2. Snapshot what the server believes the player owns, on spawn and after each pickup:

```pawn
new g_Weapon[MAX_PLAYERS][13], g_Ammo[MAX_PLAYERS][13];

stock SnapshotWeapons(playerid)
{
    new weaponid, ammo;
    for (new slot = 0; slot <= 12; slot++)
    {
        GetPlayerWeaponData(playerid, WEAPON_SLOT:slot, weaponid, ammo);
        g_Weapon[playerid][slot] = weaponid, g_Ammo[playerid][slot] = ammo;
    }
}

stock bool:HasWeapon(playerid, weaponid)
{
    if (weaponid == 0) return false;
    for (new slot = 0; slot <= 12; slot++) if (g_Weapon[playerid][slot] == weaponid) return true;
    return false;
}
```

3. Reject the claim at the RPC boundary. Return `0` to drop the packet and `1` to let it through, the same contract Pawn.RakNet uses in its own examples. Fire sources report `37` and explosions `51`, so those keep their value; nothing else may remove more than a full health bar in one event.

```pawn
const RPC_GiveTakeDamage = 115;
#define DAMAGE_CAP 100.0

stock bool:IsBlastWeapon(weaponid) return (weaponid == 51 || weaponid == 37);

IRPC:RPC_GiveTakeDamage(playerid, BitStream:bs)
{
    new bool:give, victim, weapon, bodypart;
    new Float:amount;

    BS_ReadValue(bs,
        PR_BOOL, give, PR_UINT16, victim, PR_FLOAT, amount, PR_UINT32, weapon, PR_UINT32, bodypart);

    if (!give) return 1;                       // "take" direction carries no authority
    if (victim == playerid) return 0;          // self-damage needs no packet
    if (!IsPlayerConnected(victim)) return 0;
    if (GetPlayerState(victim) == PLAYER_STATE_NONE) return 0;  // not spawned yet
    if (GetPlayerVirtualWorld(victim) != GetPlayerVirtualWorld(playerid)) return 0;
    if (GetPlayerInterior(victim) != GetPlayerInterior(playerid)) return 0;
    if (weapon < 0 || weapon > 54) return 0;   // 49-54 are damage reasons, not items
    if (!IsBlastWeapon(weapon) && (amount < 0.0 || amount > DAMAGE_CAP)) return 0;
    if (weapon >= 1 && weapon <= 46 && !HasWeapon(playerid, weapon)) return 0;
    return 1;
}
```

4. Filter BulletSync (packet `206`) before it is replicated. This is the crasher path: peers decode whatever weapon id and target id the sender wrote. Documented layout is packet id, hit type, hit id, origin XYZ, hit position XYZ, offsets XYZ, weapon id.

```pawn
const BULLET_SYNC = 206;
#define BULLET_SYNC_MIN_BITS (8 + 8 + 16 + 9 * 32 + 8)   // 328 bits

IPacket:BULLET_SYNC(playerid, BitStream:bs)
{
    new hitType, hitId, weapon, bits;
    new Float:ox, Float:oy, Float:oz, Float:hx, Float:hy, Float:hz, Float:fx, Float:fy, Float:fz;

    BS_GetNumberOfBitsUsed(bs, bits);
    if (bits < BULLET_SYNC_MIN_BITS) return 0;   // truncated packet

    BS_ReadValue(bs,
        PR_IGNORE_BITS, 8, PR_UINT8, hitType, PR_UINT16, hitId,
        PR_FLOAT, ox, PR_FLOAT, oy, PR_FLOAT, oz, PR_FLOAT, hx, PR_FLOAT, hy, PR_FLOAT, hz,
        PR_FLOAT, fx, PR_FLOAT, fy, PR_FLOAT, fz, PR_UINT8, weapon);

    if (hitType > 4) return 0;                    // documented hit types 0-4
    if (hitType == 1 && !IsPlayerConnected(hitId)) return 0;
    if (weapon < 22 || weapon > 34) return 0;     // 22-34 are the bullet weapons
    return 1;
}
```

5. Write one JSON line per decision, keep it 30 days (`find scriptfiles/ac -name '*.jsonl' -mtime +30 -delete`), and ban from the log rather than from a live guess:

```pawn
stock LogDamageEvent(playerid, issuer, weapon, Float:amount, Float:dist, const verdict[], const reason[])
{
    new File:f = fopen("ac/damage.jsonl", io_append), line[256], name[MAX_PLAYER_NAME + 1], ip[16];
    if (!f) return 0;
    GetPlayerName(playerid, name, sizeof name);
    GetPlayerIp(playerid, ip, sizeof ip);
    format(line, sizeof line,
        "{\"t\":%d,\"pid\":%d,\"name\":\"%s\",\"issuer\":%d,\"weapon\":%d,\"amount\":%.1f,\"dist\":%.1f,\"verdict\":\"%s\",\"reason\":\"%s\",\"ip\":\"%s\"}\n",
        GetTickCount(), playerid, name, issuer, weapon, amount, dist, verdict, reason, ip);
    fwrite(f, line);
    fclose(f);
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Grenade and RPG kills stop registering | `DAMAGE_CAP` applied to blast weapons | whitelist `51`/`37` in `IsBlastWeapon` before the cap check |
| Every shot from the mobile client is dropped | mobile omits the slot update, so `HasWeapon` is stale | refresh the snapshot in `OnPlayerWeaponShot` before judging |
| Server still crashes on a shot | filter attached to `OnPlayerWeaponShot`, which runs after replication | block at packet `206` so peers never decode the payload |
| Honest players banned after a respawn | inventory cleared before the snapshot | re-snapshot in `OnPlayerSpawn`, judge only while `PLAYER_STATE_ONFOOT` |

## Verification

```bash
./pawncc gamemodes/main.pwn -d3 -o gamemodes/main.amx
python3 - <<'PY'
import json, collections
rows = [json.loads(l) for l in open("scriptfiles/ac/damage.jsonl") if l.strip()]
blocked = collections.Counter(r["reason"] for r in rows if r["verdict"] == "block")
print("events", len(rows), "blocked", sum(blocked.values()))
for reason, n in blocked.most_common():
    print(f"{reason}: {n}")
PY
```

Expected output after one crasher attempt:

```text
events 6 blocked 4
damage_over_cap: 2
weapon_not_in_inventory: 1
world_mismatch: 1
```

- Manual: RPC `115` with `amount = 1000.0` leaves the victim at full health and logs `"verdict":"block"`; a normal Deagle hit 3 m away logs `"verdict":"ok"`.

## Sources (2026)

- https://open.mp/docs/scripting/callbacks/OnPlayerTakeDamage — amount is max weapon damage, old health inside the callback.
- https://open.mp/docs/scripting/callbacks/OnPlayerWeaponShot — return 0 blocks damage; fake weapon ids freeze peers.
- https://github.com/Brunoo16/samp-packet-list/wiki/RPC-List — RPC 115 `GiveTakeDamage` field order.
