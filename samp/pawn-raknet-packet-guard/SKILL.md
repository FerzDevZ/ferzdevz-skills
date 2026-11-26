---
name: pawn-raknet-packet-guard
description: Use when a packet's fields must be proven before they apply.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, security, raknet, validation]
    category: samp
---

# ValidatePacket: known id, structural size floor, then field ranges

A forged sync packet is not malformed — it is well-formed with values the client should never
send. The gate runs three checks in order: the id is one you consume, the bit length can hold
that structure, the player is under the message budget. Only then is a field read.

## When to Use

- A client reports a weapon, ammo count or health value the server never granted.
- A hit lands client-side but arrives as a bullet packet with an impossible weapon id.
- Not for floods alone — for transport limits and RPC whitelisting use `raknet-incoming-rpc-filter`.

## Compatibility & Stack Matrix (2026)

| Layer | 2026 baseline | Note |
| --- | --- | --- |
| Pawn.RakNet | `omp` branch 1.6.x | `OnIncomingPacket` / `OnIncomingRPC`; `pawnraknet.cfg` must intercept incoming |
| Server | open.mp 1.6.x | `network.messages_limit` defaults to 500 messages per second per user |
| Compiler | pawncc 3.10.10, `-d3` | a `switch` on an untagged cell avoids warning 213 |
| BitStream | `BS_GetNumberOfBitsUsed`, `BS_ReadValue`, `BS_ResetReadPointer` | natives of Pawn.RakNet 1.6.x |

## Production Implementation

1. Write the floors down once. Count only the fixed-width integer fields of each documented
   structure and ignore the floats, which is a true lower bound whatever the compression:

| id | Structure | Fixed-width fields counted | Floor |
| --- | --- | --- | --- |
| 200 | InCarSync | veh 16, lr 16, ud 16, keys 16, 6×8, trailer 16 | 120 |
| 204 | WeaponsUpdate | target 16, actor 16, 13 slots × 24 | 320 |
| 206 | BulletSync | hitType 8, hitId 16, weapon 8 | 24 |
| 207 | OnFootSync | lr/ud/keys 48, 5×8, 3×16 unsigned | 128 |
| 211 | PassengerSync | 4×16, 6×8 | 104 |

2. Hold the table as two parallel arrays so the gate is one loop, with -1 for any id the
   gamemode does not consume:

```pawn
#define GUARD_UNKNOWN   1
#define GUARD_TRUNCATED 2
#define GUARD_RATE      3
#define MAX_MSGS_SEC    150          // below network.messages_limit, so the gate fires first

new const g_FloorIds[] = { 200, 204, 206, 207, 211 };
new const g_Floors[]   = { 120, 320,  24, 128, 104 };

stock PacketFloor(packetid)
{
    for (new i; i < sizeof g_FloorIds; i++)
        if (g_FloorIds[i] == packetid) return g_Floors[i];
    return -1;
}

stock bool:ValidatePacket(playerid, packetid, BitStream:bs)
{
    if (!IsPlayerConnected(playerid)) return false;

    new floor = PacketFloor(packetid), bits;
    if (floor < 0)                       return RejectPacket(playerid, packetid, GUARD_UNKNOWN);
    BS_GetNumberOfBitsUsed(bs, bits);
    if (bits < floor || bits > 8192)     return RejectPacket(playerid, packetid, GUARD_TRUNCATED);
    if (!SpendMessage(playerid))         return RejectPacket(playerid, packetid, GUARD_RATE);
    return true;
}
```

3. Count messages in a one-second window keyed on `GetTickCount() / 1000`; a reset on a second
   boundary cannot drift and an idle player costs one integer:

```pawn
new g_MsgSecond[MAX_PLAYERS], g_MsgCount[MAX_PLAYERS], g_Rejects[MAX_PLAYERS];

stock bool:SpendMessage(playerid)
{
    new sec = GetTickCount() / 1000;
    if (g_MsgSecond[playerid] != sec)
        g_MsgSecond[playerid] = sec, g_MsgCount[playerid] = 0;
    return (++g_MsgCount[playerid] <= MAX_MSGS_SEC);
}
```

4. Validate fields at the point of reading: reset the read pointer, read the exact prefix, and
   reject the first out-of-range value so nothing is half applied:

```pawn
stock bool:ValidateWeapons(BitStream:bs)
{
    new target, actor, weapon, ammo;
    BS_ResetReadPointer(bs);
    BS_ReadValue(bs, PR_UINT16, target, PR_UINT16, actor, PR_UINT8, weapon, PR_UINT16, ammo);
    if (weapon > 46) return false;                 // 0.3.7 weapon ids stop at 46
    if (target != 65535 && target >= MAX_PLAYERS) return false;
    return (ammo <= 9999);
}
```

5. Wire the gate first in `OnIncomingPacket`, then in `OnIncomingRPC` for ids you answer.
   Returning 0 drops the packet, so the callback that would use the field never fires. Log the
   reason and escalate only on repeats — one drop is a lagging client, two hundred is a script:

```pawn
public OnIncomingPacket(playerid, packetid, BitStream:bs)
{
    return ValidatePacket(playerid, packetid, bs) ? 1 : 0;
}

public OnIncomingRPC(playerid, rpcid, BitStream:bs)
{
    if (rpcid != 100) return 1;                    // the one RPC this script reads
    return ValidateWeapons(bs) ? 1 : 0;
}

stock bool:RejectPacket(playerid, packetid, reason)
{
    new line[128], f = fopen("ac/guard.log", io_append);
    if (f)
    {
        format(line, sizeof line, "GUARD|%d|%d|%d\n", playerid, packetid, reason);
        fwrite(f, line);
        fclose(f);
    }
    if (++g_Rejects[playerid] > 200) Kick(playerid);
    return false;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Whole server rubber-bands after enabling the gate | sync ids dropped because a floor is too high | log `bits` per id for one session, then set floors from real traffic |
| Gate never rejects anything | `InterceptIncomingPacket` false in `pawnraknet.cfg` | set it true and restart the server |
| Legitimate players kicked in bursts | kick threshold reached during packet loss | raise the counter ceiling, keep the rate drop |
| Weapon still wrong after the gate | field validated in another callback than the one reading it | validate at read time, beside `BS_ReadValue` |
| Crash right after a drop | read pointer left mid-stream by a failed read | `BS_ResetReadPointer` before every read |

## Verification

Replay a crafted packet with `PR_EmulateIncomingRPC` on a test server, then aggregate the log:

```bash
python3 -c "import collections;r=[l.split('|') for l in open('scriptfiles/ac/guard.log')];print('rejects',len(r));print('by_id',dict(sorted(collections.Counter(x[2] for x in r).items())));print('by_reason',dict(sorted(collections.Counter(x[3].strip() for x in r).items())))"
```

Expected after one emulated truncated 207 and one 204 with `weapon = 200`:

```text
rejects 3
by_id {'204': 1, '207': 2}
by_reason {'1': 1, '2': 1, '4': 1}
```

Reason `1` is unknown id, `2` truncated, `4` a bad field; a clean client writes no lines in ten minutes, and no state change follows a rejection.

## Sources (2026)

- https://github.com/katursis/Pawn.RakNet/wiki/Functions — `BS_GetNumberOfBitsUsed`, `BS_ReadValue`, `BS_ResetReadPointer`, `PR_EmulateIncomingRPC`.
- https://github.com/katursis/Pawn.RakNet/wiki/Synchronization-structures — field layout of InCarSync, OnFootSync, WeaponsUpdate, PassengerSync.
- https://open.mp/docs/server/config.json — `network.messages_limit` default of 500 per second and the other RakNet bans.
