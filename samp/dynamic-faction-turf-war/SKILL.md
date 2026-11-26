---
name: dynamic-faction-turf-war
description: Use when turf ownership or capture progress drifts.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, gameplay, gangs, persistence]
    category: samp
---

# Faction turf war: occupancy counters, one timer, durable ownership

## When to Use

- A gang captures a zone with nobody standing in it, or a capture finishes for a player who already left.
- Progress advances twice, stutters, or resets after a restart.
- Zone colour and the database disagree about the owner.

## Compatibility & Stack Matrix (2026)

| Piece | 2026 reality | What it means here |
| --- | --- | --- |
| Zone id | `GangZoneCreate(minX, minY, maxX, maxY)` returns `-1` on failure, 1024 zones max | one zone per turf, created once at boot |
| Presence | `UseGangZoneCheck(zone, true)` then `OnPlayerEnterGangZone` / `OnPlayerLeaveGangZone` | counters on events, no per-tick position scanning |
| Persistence | SQLite via `db_open` / `db_query` / `db_next_row` | restore before the first tick, save on every flip |

## Production Implementation

1. One record per turf, geometry included so a reload can rebuild the zones from data:

```pawn
#define MAX_TURFS        64
#define TURF_MIN_ATTACK  3
#define TURF_CAPTURE_MS  120000
#define TURF_TICK_MS     1000
#define TURF_DECAY       2.0
enum E_TURF {
    tz_zone, tz_owner, tz_challenger, tz_attackers, tz_defenders,
    Float:tz_progress, bool:tz_capturing,
    Float:tz_minX, Float:tz_minY, Float:tz_maxX, Float:tz_maxY
};
new g_Turf[MAX_TURFS];
new g_TurfCount; new DB:g_TurfDB;
new g_PlayerTurf[MAX_PLAYERS] = { -1, ... };
```

2. Load ownership before the first tick from the table the save writes, so a restart cannot resurrect a stale colour:

```pawn
stock Turf_Load()
{
    g_TurfDB = db_open("scriptfiles/turf.db");
    if (g_TurfDB == DB:0) { print("[turf] db_open failed"); return 0; }
    db_query(g_TurfDB, "CREATE TABLE IF NOT EXISTS turf (id INTEGER PRIMARY KEY, owner INTEGER NOT NULL DEFAULT 0)");
    new DBResult:res = db_query(g_TurfDB, "SELECT id, owner FROM turf");
    for (new i = 0, n = db_num_rows(res); res != DBResult:0 && i < n; i++)
    {
        new id = db_get_field_int(res, 0);
        if (id >= 0 && id < g_TurfCount) g_Turf[id].tz_owner = db_get_field_int(res, 1);
        db_next_row(res);
    }
    if (res != DBResult:0) db_free_result(res);
    for (new i = 0; i < g_TurfCount; i++) Turf_Paint(i);
    return 1;
}
```

3. Count occupancy in the zone callbacks, and treat a repeated enter for the same zone as a no-op so a duplicate event cannot double-count:

```pawn
public OnPlayerEnterGangZone(playerid, zoneid)
{
    new index = Turf_FromZone(zoneid);
    if (index < 0 || g_PlayerTurf[playerid] == index) return 1;      // duplicate event
    Turf_Leave(playerid);
    g_PlayerTurf[playerid] = index;
    if (GetPlayerTeam(playerid) == g_Turf[index].tz_owner) g_Turf[index].tz_defenders++;
    else {
        g_Turf[index].tz_attackers++;
        if (!g_Turf[index].tz_capturing) Turf_Begin(index, GetPlayerTeam(playerid));
    }
    return 1;
}
public OnPlayerLeaveGangZone(playerid, zoneid)
{
    new index = g_PlayerTurf[playerid];
    if (index < 0) return 1;
    if (GetPlayerTeam(playerid) == g_Turf[index].tz_owner) g_Turf[index].tz_defenders--;
    else g_Turf[index].tz_attackers--;
    if (g_Turf[index].tz_defenders < 0) g_Turf[index].tz_defenders = 0;
    g_PlayerTurf[playerid] = -1;
    return 1;
}
```

4. One repeating timer advances every capture; attackers below the minimum, or defenders matching them, decay the bar:

```pawn
forward Turf_Tick();
public Turf_Tick()
{
    new Float:step = 100.0 / (float(TURF_CAPTURE_MS) / float(TURF_TICK_MS));
    for (new i = 0; i < g_TurfCount; i++)
    {
        if (!g_Turf[i].tz_capturing) continue;
        new bool:stalled = (g_Turf[i].tz_attackers < TURF_MIN_ATTACK || g_Turf[i].tz_attackers <= g_Turf[i].tz_defenders);
        if (stalled) g_Turf[i].tz_progress -= TURF_DECAY; else g_Turf[i].tz_progress += step;
        if (g_Turf[i].tz_progress <= 0.0) { Turf_Cancel(i); continue; }
        Turf_Paint(i);
        if (g_Turf[i].tz_progress >= 100.0) Turf_Complete(i);
    }
    return 1;
}
```

5. The flip is one atomic function: owner, counters, colour, row and announce move together, and `INSERT OR REPLACE` makes a retried save idempotent:

```pawn
stock Turf_Complete(index)
{
    new query[128];
    g_Turf[index].tz_owner = g_Turf[index].tz_challenger;
    g_Turf[index].tz_progress = 0.0; g_Turf[index].tz_capturing = false;
    g_Turf[index].tz_challenger = 0;
    format(query, sizeof query, "INSERT OR REPLACE INTO turf (id, owner) VALUES (%d, %d)",
        index, g_Turf[index].tz_owner);
    db_query(g_TurfDB, query);
    Turf_Paint(index);
    printf("[turf] owner changed id=%d owner=%d", index, g_Turf[index].tz_owner);
}
```

6. Close the leaks counters always have: leave on death and disconnect before the slot is reset, and enable the zone check at boot:

```pawn
public OnPlayerDeath(playerid, killerid, WEAPON:reason) { Turf_Leave(playerid); return 1; }
public OnPlayerDisconnect(playerid, reason) { Turf_Leave(playerid); return 1; }
public OnGameModeInit()
{
    Turf_Load();
    for (new i = 0; i < g_TurfCount; i++) UseGangZoneCheck(g_Turf[i].tz_zone, true);
    SetTimer("Turf_Tick", TURF_TICK_MS, true);
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Capture with an empty zone | progress advanced on a timer without a presence check | require `tz_attackers >= TURF_MIN_ATTACK` every tick |
| Progress jumps or runs twice | two timers started, or a per-zone timer left alive | one `SetTimer`, started once in `OnGameModeInit` |
| Counters drift negative or high | leave missed after a teleport, death or disconnect | call `Turf_Leave` from death, disconnect and teleports |
| Owner reverts after restart | ownership only in memory | `Turf_Load` before the first tick, save on every flip |
## Verification

```bash
pawncc gamemodes/turf.pwn -i include -o /tmp/turf.amx -d3
sqlite3 scriptfiles/turf.db "SELECT id, owner FROM turf ORDER BY id;"
grep -h "\[turf\]" server_log.txt | tail -10
```

Expected: the compile is clean; the query prints one row per turf with the same owners the server logged, so a restart keeps ownership; the log tail shows `[turf] owner changed id=N owner=K` only after a full `TURF_CAPTURE_MS` window with at least `TURF_MIN_ATTACK` attackers present, and nothing when the same players leave after ten seconds.

## Sources (2026)

- https://open.mp/docs/scripting/functions/GangZoneCreate
- https://open.mp/docs/scripting/functions/UseGangZoneCheck
- https://open.mp/docs/scripting/functions/IsPlayerInGangZone
