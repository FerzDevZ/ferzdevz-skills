---
name: android-mobile-client-sync-guard
description: Use when mobile SA-MP clients desync after alt-tab.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mobile, sync, anticheat]
    category: samp
---

# Mobile sync guard: validate the resume burst instead of trusting it

## When to Use

- Android players return from alt-tab, a notification or a Wi-Fi to mobile-data handover and land in a wall, freeze, or get kicked for speed.
- The log shows a multi-second hole in one player's updates followed by a burst of packets.
- Your anticheat reads the first packet after the gap as a teleport, because it measures from the last position before the pause.

## Compatibility & Stack Matrix (2026)

| Piece | 2026 reality | What it means for the guard |
| --- | --- | --- |
| Client mix | PC 0.3.7, open.mp launcher, SA-MP Android builds | branch on observed timing, never on a client build string |
| `network.allow_037_clients` | bool, default `true` in `config.json` | keep it enabled while mobile players exist; the guard must not depend on it |
| `network.messages_limit` | 500 messages/second per player | a resume burst above that is dropped by the server, and the drop looks like desync |
| `network.player_timeout` | 10000 ms | a gap longer than this is a reconnect; the slot is already gone |
| Position truth | `GetPlayerPos` sampled by the server | delta over elapsed time is the only speed number that is not a client claim |

## Production Implementation

1. Keep one anchor per player: the last position the server sampled itself. Every judgement is a delta from it, never a value the client sent.

```pawn
#define SYNC_GAP_MS       2000      // silence that counts as a resume
#define SYNC_GRACE_MS     3000      // widened threshold after a resume
#define SYNC_FOOT_MAX     9.0       // units/second, calibrate per server
#define SYNC_VEHICLE_MAX  90.0
#define SYNC_GRACE_MAX    200.0     // finite: a resume is not a licence
#define SYNC_STRIKES_MAX  3

new g_LastTick[MAX_PLAYERS];        // last update the server saw
new g_AnchorTick[MAX_PLAYERS];      // when the anchor was sampled
new Float:g_AnchorX[MAX_PLAYERS];
new Float:g_AnchorY[MAX_PLAYERS];
new Float:g_AnchorZ[MAX_PLAYERS];
new g_GraceUntil[MAX_PLAYERS];
new g_Strikes[MAX_PLAYERS];
new g_Resumes[MAX_PLAYERS];         // resumes seen this session
```

2. Time the gap in `OnPlayerUpdate`, which fires per client update. Never return 0 here to protect a player: that stops replication for everyone else and turns a hiccup into a ghost.

```pawn
public OnPlayerUpdate(playerid)
{
    new now = GetTickCount();
    new elapsed = now - g_LastTick[playerid];

    if (g_LastTick[playerid] != 0 && elapsed >= SYNC_GAP_MS)
        Sync_OnResume(playerid, elapsed);
    g_LastTick[playerid] = now;
    Sync_Validate(playerid, now);
    return 1;
}
```

3. A resume forgives nothing structural: it widens the speed threshold for a fixed window and logs the event. `elapsed` includes the pause, so a normal walk over several seconds lands far under the limit.

```pawn
stock Sync_OnResume(playerid, gap)
{
    g_GraceUntil[playerid] = GetTickCount() + SYNC_GRACE_MS;
    g_Resumes[playerid]++;
    printf("[sync] resume player=%d gap=%dms grace=%dms", playerid, gap, SYNC_GRACE_MS);
}
```

4. Validate with two independent checks. Speed alone is noisy on a bad link; keys against displacement catches the client that claims no input and still moves, which is what airbreak and teleport do.

```pawn
stock bool:Sync_KeysExplainMovement(playerid)
{
    new KEY:keys, updown, leftright;
    GetPlayerKeys(playerid, keys, updown, leftright);
    if (IsPlayerInAnyVehicle(playerid)) return true;              // physics moves you
    if (GetPlayerState(playerid) != PLAYER_STATE_ONFOOT) return true;
    return (updown != 0 || leftright != 0
        || (keys & KEY_SPRINT) != 0 || (keys & KEY_JUMP) != 0);
}
stock Sync_Validate(playerid, now)
{
    if (!IsPlayerConnected(playerid)) return 0;
    new Float:x, Float:y, Float:z;
    GetPlayerPos(playerid, x, y, z);
    new elapsed = now - g_AnchorTick[playerid];
    if (elapsed < 50) return 0;                                   // too short to judge

    new Float:dx = x - g_AnchorX[playerid];
    new Float:dy = y - g_AnchorY[playerid];
    new Float:dz = z - g_AnchorZ[playerid];
    new Float:dist = floatsqroot(dx * dx + dy * dy + dz * dz);
    new Float:speed = dist / (float(elapsed) / 1000.0 + 0.001);
    new Float:limit = IsPlayerInAnyVehicle(playerid) ? SYNC_VEHICLE_MAX : SYNC_FOOT_MAX;
    if (now < g_GraceUntil[playerid]) limit = SYNC_GRACE_MAX;
    if (speed > limit && !Sync_KeysExplainMovement(playerid))
    {
        if (++g_Strikes[playerid] >= SYNC_STRIKES_MAX)
        {
            printf("[sync] flag player=%d speed=%.1f limit=%.1f dist=%.1f grace=%d",
                playerid, speed, limit, dist, (now < g_GraceUntil[playerid]));
            g_Strikes[playerid] = 0;                              // hand to the evidence pipeline
        }
    }
    else if (speed <= SYNC_FOOT_MAX) g_Strikes[playerid] = 0;     // decay on clean movement

    g_AnchorX[playerid] = x;
    g_AnchorY[playerid] = y;
    g_AnchorZ[playerid] = z;
    g_AnchorTick[playerid] = now;
    return 1;
}
```

5. Every server-side teleport must move the anchor, or the next update looks like a 500-unit jump. Call `Sync_Reanchor` from spawn, jail and admin teleport; reset state on connect so a recycled slot never inherits a grace window:

```pawn
stock Sync_Reanchor(playerid)
{
    GetPlayerPos(playerid, g_AnchorX[playerid], g_AnchorY[playerid], g_AnchorZ[playerid]);
    g_AnchorTick[playerid] = GetTickCount();
    g_Strikes[playerid] = 0;
    g_GraceUntil[playerid] = 0;
}
stock Sync_Reset(playerid)
{
    g_LastTick[playerid] = 0;
    g_AnchorTick[playerid] = GetTickCount();
    g_GraceUntil[playerid] = 0;
    g_Strikes[playerid] = 0;
    g_Resumes[playerid] = 0;
}
```

6. Rate-limit the resume path itself: compare `NetStats_MessagesRecvPerSecond` with `network.messages_limit` before blaming the player. A client that wakes every two seconds is a broken build or a replay, visible in the message budget, not the delta.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Mobile players kicked only after alt-tab | anticheat measures from the pre-pause position with no elapsed time | divide by real elapsed ms, as `Sync_Validate` does |
| Player is a ghost for everyone after resume | callback returned 0 during the grace window | always return 1 from `OnPlayerUpdate`; flag instead of freezing |
| Kicks after every admin teleport | anchor not moved when the server set the position | call `Sync_Reanchor` after every spawn, jail and teleport |
| Real cheaters survive because "mobile" | grace applied by client type or left open-ended | grace is time-boxed and threshold-based only |
| Desync every few seconds on one device | burst keeps hitting `network.messages_limit` | log resume counts, raise the limit only for a confirmed build |
## Verification

```bash
pawncc gamemodes/sync_guard.pwn -i include -o /tmp/sg.amx -d3
./omp-server --dump-config | grep -E '"network\.(messages_limit|player_timeout|on_foot_sync_rate)"'
grep -h "\[sync\]" server_log.txt | tail -20
```

Expected: `pawncc` exits 0 with no warnings; the dump prints `"messages_limit": 500`, `"player_timeout": 10000` and `"on_foot_sync_rate": 30`, so the 2000 ms gap constant sits well under the timeout; the log tail has one `[sync] resume player=N gap=...` line per alt-tab and no `[sync] flag` line for a player who only walked during the grace window.

## Sources (2026)

- https://open.mp/docs/server/config.json
- https://open.mp/docs/scripting/callbacks/OnPlayerUpdate
- https://open.mp/docs/scripting/functions/GetPlayerKeys
