---
name: raknet-packet-desync-debug
description: Use when RPC sizes mismatch between client builds.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, network, raknet]
    category: samp
---

# Find the desync between a client build and your RPC reader

A desync is not a mystery: the packet arrives with a bit length that does not match the layout
your reader assumes, so every field after the mismatch is garbage. Measure the length first,
compare against the layout for that connection, and only then read.

## When to Use

- A feature works for one group of clients and silently does nothing for another.
- Positions, health or vehicle ids arrive as nonsense after a client update.
- You are about to filter a packet and need to know its real size before blocking anything.

## Compatibility & Stack Matrix (2026)

| Item | Value | Note |
| --- | --- | --- |
| Plugin | Pawn.RakNet `1.6.0-omp` | ships a separate open.mp build |
| Incoming packet hook | `OnIncomingPacket(playerid, packetid, BitStream:bs)` | fires before script handlers |
| Incoming RPC hook | `OnIncomingRPC(playerid, rpcid, BitStream:bs)` | RPC body, no packet id byte |
| Typed handlers | `IPacket:207(playerid, BitStream:bs)` | run after the general publics |
| Size query | `BS_GetNumberOfBitsUsed(bs, bits)` | two arguments, output by reference |
| Skip id | `BS_IgnoreBits(bs, 8)` | packet id is one byte |
| Drop a packet | `return 0` from the handler | the return value propagates to RakNet |
| Legacy clients | `network.allow_037_clients` in `config.json` | one server, two layouts |

The same server can carry legacy 0.3.7 and newer client builds at once, and their sync layouts
differ: derive layout from measured bit lengths, never from a version string.

## Production Implementation

1. Add a trace that is compiled in only for debug, and is sampled so a full server does not
   turn the log into a disk test. Record what the packet claims to be, not what you hope it is.

```pawn
#define NET_TRACE      (1)
#define TRACE_SAMPLES  (16)
#define PACKET_PLAYER_SYNC (207)

new g_TraceBits[MAX_PLAYERS][TRACE_SAMPLES];
new g_TraceIdx[MAX_PLAYERS];
new g_TraceBad[MAX_PLAYERS];

public OnGameModeInit()
{
    printf("NETTRACE on=%d samples=%d", NET_TRACE, TRACE_SAMPLES);   // positive control
    return 1;
}
```

2. Measure every packet once. `BS_GetNumberOfBitsUsed` takes the bitstream plus an output
   variable; the one-argument call that circulates in old snippets gives you nothing.

```pawn
public OnIncomingPacket(playerid, packetid, BitStream:bs)
{
    if (!NET_TRACE || playerid == INVALID_PLAYER_ID) return 1;

    new bits;
    BS_GetNumberOfBitsUsed(bs, bits);

    g_TraceBits[playerid][g_TraceIdx[playerid]] = bits;
    g_TraceIdx[playerid] = (g_TraceIdx[playerid] + 1) % TRACE_SAMPLES;

    if (packetid == PACKET_PLAYER_SYNC && bits < 40)   // id byte plus the fixed header cannot fit
    {
        g_TraceBad[playerid]++;
        printf("DESYNC player=%d packet=%d bits=%d", playerid, packetid, bits);
    }
    return 1;
}
```

3. Turn the ring buffer into a per-player signature at disconnect. Two players with different
   clients produce different multisets of lengths, which is exactly the layout proof.

```pawn
stock Trace_Signature(playerid)
{
    new bits;
    for (new i = 0; i < TRACE_SAMPLES; i++) bits += g_TraceBits[playerid][i];
    printf("TRACE player=%d min=%d sum=%d bad=%d", playerid,
        g_TraceBits[playerid][0], bits, g_TraceBad[playerid]);
    return bits;
}
```

4. Read defensively: check the length, read into locals, and only then copy into live state.
   A half-applied packet is worse than a dropped one because nothing downstream can tell.

```pawn
IPacket:PACKET_PLAYER_SYNC(playerid, BitStream:bs)
{
    new bits;
    BS_GetNumberOfBitsUsed(bs, bits);
    if (bits < 40) return 0;          // drop, do not half-read

    BS_IgnoreBits(bs, 8);             // packet id
    new Float:x, Float:y, Float:z;
    BS_ReadFloat(bs, x);
    BS_ReadFloat(bs, y);
    BS_ReadFloat(bs, z);

    Sync_ApplyPosition(playerid, x, y, z);   // live state touched only after a full read
    return 1;
}
```

5. When a second layout exists, key it on the observed length and store the choice per player.
   Re-measure after reconnect: the same account can arrive on a different build.

6. Block only what you can prove. `return 0` stops the packet for that player, so a filter that
   skips the length check first drops legitimate traffic from any newer client build.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Logged size is always 0 | `BS_GetNumberOfBitsUsed(bs)` called with one argument | pass an output variable: `BS_GetNumberOfBitsUsed(bs, bits)` |
| Nobody can move, no errors | handler returns 0 on every packet | return 1 and only block on a failed length check |
| Float reads are nonsense | packet id byte not skipped | `BS_IgnoreBits(bs, 8)` before the first field |
| Desync only for part of the server | a newer build's layout versus legacy 0.3.7 | branch on measured length, not on a version string |
| State half-updated after a bad packet | fields written while reading | read into locals, assign after the last read |
| `BS_*` natives missing at run time | Pawn.RakNet absent or the SA-MP build on open.mp | install the `1.6.0-omp` build and list it in `runtime.plugins` |

## Verification

Compile, boot, and confirm the trace is actually on before trusting a quiet log:

```bash
sampctl build 2>&1 | tail -2
grep -m1 "NETTRACE" log.txt
```

```text
Build complete; written to gamemodes/main.amx
NETTRACE on=1 samples=16
```

Then, after ten minutes of normal play, assert that no player produced a bad length:

```bash
grep -c "DESYNC" log.txt
grep "TRACE player=" log.txt | tail -2
```

```text
0
TRACE player=3 min=2640 sum=41248 bad=0
TRACE player=4 min=2640 sum=41248 bad=0
```

Matching `min` values across both players means one layout server-wide. Different values with
`bad=0` mean both layouts are handled. Any `DESYNC` line names the player and the packet id.

## Sources (2026)

- https://github.com/katursis/Pawn.RakNet/wiki/Callbacks
- https://github.com/katursis/Pawn.RakNet/blob/master/src/Pawn.RakNet.inc
- https://open.mp/docs/server/config.json
