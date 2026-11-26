---
name: raknet-incoming-rpc-filter
description: Use when malformed RPCs or packet floods reach the script.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, security, networking]
    category: samp
---

# Incoming RPC filter: whitelist, size-check, then rate-limit

## When to Use

- The log shows a script crash or an AMX error right after one client connects.
- A single player can flood the server with chat or dialog traffic.
- You want a cheap gate in front of Pawn callbacks that already trust their arguments.
- If the payload is a valid RPC with forged field values, use the per-topic shields instead (`dialog-spoofing-validation`, `fake-kill-bullet-crasher-shield`).

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.4.x 2026 builds | `network.messages_limit` defaults to 500 messages per second |
| SA-MP server | 0.3.7-R5, 0.3.DL-R1 | no built-in limiter, plugin only |
| Pawn.RakNet | `omp` branch, 1.6.x | `OnIncomingPacket` / `OnIncomingRPC`, config in `pawnraknet.cfg` |
| pawncc | 3.10.11 or newer | `-d3`; `switch` on an untagged int avoids 213 |

## Production Implementation

1. Spend the free protection first: raise the transport limits in `config.json` before writing a line of Pawn. `messages_limit` is per second per user, `acks_limit` and `message_hole_limit` are DoS knobs, and `limits_ban_time` is how long a bad connect stays banned:

```bash
python3 - <<'PY'
import json
c = json.load(open("config.json"))
c.setdefault("network", {}).update(messages_limit=500, acks_limit=3000,
    message_hole_limit=3000, limits_ban_time=60000)
json.dump(c, open("config.json", "w"), indent=2)
print("network limits written")
PY
```

2. Whitelist the packet ids your gamemode actually consumes. The documented sync ids are `200` in-car, `203` aim, `204` weapons, `205` stats, `206` bullet, `207` on-foot, `208` markers, `209` unoccupied, `210` trailer, `211` passenger, `212` spectating; `20` carries the RPCs themselves. Anything else is dropped before Pawn sees it:

```pawn
new const g_AllowedPackets[] = { 20, 200, 201, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212 };

stock bool:IsAllowedPacket(packetid)
{
    for (new i = 0; i < sizeof g_AllowedPackets; i++)
        if (g_AllowedPackets[i] == packetid) return true;
    return false;
}
```

3. Count per player per second with a one-second window, and size-check the RPCs that index arrays. Keep the ceiling below `network.messages_limit`, so your gate reacts before the transport bans the address and hides the reason. DialogResponse (`62`) is `INT16 dialogid, UINT8 response, INT16 listitem, UINT8 textlen, char[] text`, so 48 bits is its floor:

```pawn
#define MSG_PER_SEC 120
new g_MsgSecond[MAX_PLAYERS], g_MsgCount[MAX_PLAYERS];

stock bool:AllowMessage(playerid)
{
    new sec = GetTickCount() / 1000;
    if (g_MsgSecond[playerid] != sec)
        g_MsgSecond[playerid] = sec, g_MsgCount[playerid] = 0;
    return (++g_MsgCount[playerid] <= MSG_PER_SEC);
}

public OnIncomingPacket(playerid, packetid, BitStream:bs)
{
    if (!IsPlayerConnected(playerid)) return 0;               // 0 = drop
    if (!IsAllowedPacket(packetid)) return DropPacket(playerid, packetid, 0, "unknown_packet");
    if (!AllowMessage(playerid)) return DropPacket(playerid, packetid, 0, "rate_limit");
    return 1;                                                 // 1 = let it through
}

public OnIncomingRPC(playerid, rpcid, BitStream:bs)
{
    new bits;
    BS_GetNumberOfBitsUsed(bs, bits);

    switch (rpcid)
    {
        case 62:  if (bits < 48 || bits > 4096) return DropPacket(playerid, rpcid, bits, "size_mismatch");
        case 101: if (bits < 8 || bits > 8 * 129) return DropPacket(playerid, rpcid, bits, "size_mismatch");
        default: if (bits > 8192) return DropPacket(playerid, rpcid, bits, "size_mismatch");
    }
    return 1;
}
```

4. Log the drop with the id, the bit length and the reason, then escalate on repeats. Never kick on the first drop: a lagging client resends out of order and looks like a flood:

```pawn
new g_Drops[MAX_PLAYERS], g_DropSecond[MAX_PLAYERS];

stock DropPacket(playerid, id, bits, const reason[])
{
    new sec = GetTickCount() / 1000, line[192], name[MAX_PLAYER_NAME + 1];
    if (g_DropSecond[playerid] != sec) g_DropSecond[playerid] = sec, g_Drops[playerid] = 0;
    g_Drops[playerid]++;

    GetPlayerName(playerid, name, sizeof name);
    new File:f = fopen("ac/rpc.log", io_append);
    if (f)
    {
        format(line, sizeof line, "RPC_DROP|%d|%d|%d|%s|%s\n", playerid, id, bits, reason, name);
        fwrite(f, line);
        fclose(f);
    }
    if (g_Drops[playerid] > 200) Kick(playerid);              // 200 drops in one second
    return 0;
}
```

5. Keep `pawnraknet.cfg` honest: incoming interception must be on or none of this runs, and `UseCaching` conflicts with YSI:

```text
InterceptIncomingPacket (true)
InterceptIncomingRPC (true)
UseCaching (false)
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Whole server rubber-bands after enabling the filter | sync packets dropped instead of counted | return 1 for allowed ids; only `DropPacket` on unknown ids and rate excess |
| Nothing is filtered at all | `InterceptIncomingPacket` left at `false` | set it to `true` in `pawnraknet.cfg` and restart |
| Kick waves during a DDoS | transport already banning, filter banning too | raise `network.messages_limit`, keep `MSG_PER_SEC` lower |
| Filter works but crashes remain | crash is in a valid RPC with bad field values | add the per-topic validation shield for that RPC |

## Verification

```bash
python3 -c "import json;print('messages_limit', json.load(open('config.json'))['network']['messages_limit'])"
grep -c 'InterceptIncomingRPC (true)' pawnraknet.cfg
python3 - <<'PY'
import collections
rows = [l.strip().split("|") for l in open("scriptfiles/ac/rpc.log") if l.startswith("RPC_DROP")]
by_rpc = collections.Counter(r[2] for r in rows)
by_reason = collections.Counter(r[4] for r in rows)
print("drops", len(rows))
print("by_rpc", dict(sorted(by_rpc.items())))
print("by_reason", dict(sorted(by_reason.items())))
PY
```

Expected output on a server that has seen one dialog flood and one RPC loop:

```text
messages_limit 500
1
drops 5
by_rpc {'115': 3, '62': 2}
by_reason {'rate_limit': 3, 'size_mismatch': 2}
```

- Manual: play for ten minutes with the filter on; `rpc.log` stays empty for legitimate clients, and a replayed packet sent with `PR_EmulateIncomingRPC` produces a drop line with the same id.

## Sources (2026)

- https://open.mp/docs/server/config.json — `network.messages_limit`, `acks_limit`, `limits_ban_time`.
- https://github.com/katursis/Pawn.RakNet/wiki/Callbacks — `OnIncomingPacket` / `OnIncomingRPC` signatures and return contract.
- https://github.com/katursis/Pawn.RakNet/wiki/Packet-List — documented packet ids 200-212.
