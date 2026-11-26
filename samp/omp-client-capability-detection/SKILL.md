---
name: omp-client-capability-detection
description: Use when features must vary per client build.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, client, compat, telemetry]
    category: samp
---

# Decide client capabilities from server-side signals only

The server knows more about a connection than the client will admit. open.mp identifies
launcher clients during the handshake, and the runtime either accepts legacy 0.3.7 clients or
it does not. Everything else, including the version string, is text the client chose to send.

## When to Use

- A feature only renders on part of the player base: model previews, launcher URLs, HUD density.
- You need the real population split before deciding whether to drop 0.3.7 support.
- A player reports a UI that does not fit, and you need a flag rather than a guess.

## Compatibility & Stack Matrix (2026)

| Signal | Where it comes from | Authority | Safe to use for |
| --- | --- | --- | --- |
| `IsPlayerUsingOmp` | launcher handshake, native since 1.4.0.2779 | authoritative, server-side | launcher-only presentation |
| `GetPlayerVersion` | string supplied by the client | untrusted, self-reported | telemetry and logs |
| `network.allow_037_clients` | `config.json`, read at deploy | authoritative | whether legacy clients can connect |
| Custom model support | server config, not the client | authoritative | which model ids you may assign |
| Mobile / Android client | no open.mp native exists | none | presentation only |
| Packet encryption | server config plus launcher | authoritative | whether to advertise the launcher |

`IsPlayerUsingOmp` is the one per-player fact the server establishes itself. The docs describe
`GetPlayerVersion` as "as reported by the player", so it is evidence, never a gate.

## Production Implementation

1. Fix the capability set in one enum, and keep it about rendering. A capability answers
   "what can I draw", never "what is this player allowed to do".

```pawn
enum E_CLIENT_CAPS
{
    bool:capLauncher,     // open.mp launcher, server-verified
    bool:capLegacy,       // connected down the 0.3.7 path
    bool:capRichHud,      // room for the wide HUD
    bool:capModelPreview  // 3D previews in TextDraws
};

new g_Caps[MAX_PLAYERS][E_CLIENT_CAPS];
```

2. Capture once at connect, from the native alone. "Not launcher" means "unknown
   presentation", not "modified client": plenty of players still run plain 0.3.7.

```pawn
public OnPlayerConnect(playerid)
{
    new bool:launcher = IsPlayerUsingOmp(playerid) != 0;

    g_Caps[playerid][capLauncher]     = launcher;
    g_Caps[playerid][capLegacy]       = !launcher;
    g_Caps[playerid][capRichHud]      = launcher;
    g_Caps[playerid][capModelPreview] = launcher;

    printf("CAP player=%d launcher=%d legacy=%d", playerid,
        g_Caps[playerid][capLauncher], g_Caps[playerid][capLegacy]);
    return 1;
}
```

3. Keep the version string out of the struct. Read it into a bounded log line, then throw it
   away; comparing it with `strcmp` to pick a code path is the spoofable version of this skill.
   The function returns 0 for a player that does not exist, so check that before printing.

```pawn
stock Cap_LogVersion(playerid)
{
    new version[24];
    if (GetPlayerVersion(playerid, version, sizeof version) == 0) return 0;
    printf("CAPVER player=%d ver=%s", playerid, version);   // telemetry only
    return 1;
}
```

4. Reset on disconnect. Player ids are recycled, and a stale `capRichHud` from the previous
   session is how a legacy client ends up drawing the wide HUD.

```pawn
public OnPlayerDisconnect(playerid, reason)
{
    g_Caps[playerid][capLauncher]     = false;
    g_Caps[playerid][capLegacy]       = false;
    g_Caps[playerid][capRichHud]      = false;
    g_Caps[playerid][capModelPreview] = false;
    return 1;
}
```

5. Gate presentation only. Gameplay code must never branch on `g_Caps`: a legacy player still
   buys the same car, they just get a 2D sprite instead of a rotating model.

```pawn
stock Cap_ShowVehicleCard(playerid, model)
{
    if (g_Caps[playerid][capModelPreview]) return Card_ShowPreview(playerid, model);
    return Card_ShowSprite(playerid, model);
}
```

6. Settle the legacy policy at deploy time, in `config.json`, not in the script:

```json
{
  "network": { "allow_037_clients": false }
}
```

With that false, `capLegacy` can never become true and the whole legacy branch is dead code
you can delete instead of maintaining two UIs forever.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Compile error on `IsPlayerUsingOmp` | includes older than 1.4.0.2779 | update the open.mp includes, never `#define` a fake native |
| Every player reported as legacy | server still allows 0.3.7 and players use it | expected; check `network.allow_037_clients` before blaming the native |
| A launcher player still misses launcher features | capability read before the handshake completed | evaluate in `OnPlayerConnect`, re-evaluate once on first spawn |
| Modified client bypasses a restriction | rule gated on `GetPlayerVersion` or on a client-sent flag | move the rule server-side; version strings are self-reported |
| Recycled id inherits the previous HUD | caps never reset on disconnect | clear the struct in `OnPlayerDisconnect` |
| Population split looks wrong in logs | logging the raw version string | log the derived booleans and count them at disconnect |

## Verification

Compile and count the server-side calls; the native appears exactly once per connect path:

```bash
grep -c "IsPlayerUsingOmp" gamemodes/main.pwn
sampctl build 2>&1 | tail -2
```

```text
1
Build complete; written to gamemodes/main.amx
```

Then connect one launcher client and one plain 0.3.7 client and read the log:

```bash
grep -E "^CAP " log.txt | tail -4
```

```text
CAP player=3 launcher=1 legacy=0
CAP player=4 launcher=0 legacy=1
```

Two different flag pairs from the same code path is the proof. If both lines are identical,
the server is not separating the connections and a client-side assumption has leaked in.

## Sources (2026)

- https://open.mp/docs/scripting/functions/IsPlayerUsingOmp
- https://open.mp/docs/scripting/functions/GetPlayerVersion
- https://open.mp/docs/server/config.json
