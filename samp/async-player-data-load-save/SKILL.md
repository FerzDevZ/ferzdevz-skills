---
name: async-player-data-load-save
description: Use when player data load or save blocks or races.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql, persistence]
    category: samp
---

# Async player data: load once, save once

## When to Use
- Login takes hundreds of milliseconds because a `SELECT` runs on the main thread.
- Money resets after a fast reconnect, or one player's save lands on another player's row.
- The last minutes of a session are lost because the save only ran on a timer.

## Compatibility & Stack Matrix (2026)
| Component | Version | Notes |
| --- | --- | --- |
| BlueG MySQL | R41-4 or newer | `mysql_tquery` / `mysql_pquery`, `cache_*` reads, `mysql_escape_string` |
| open.mp MySQL component | component build | different API surface; see `omp-mysql-component-setup` |
| YSI y_timers | 5.x | `ptask`/`timer` drive the debounce and flush without `SetTimerEx` bookkeeping |
| MariaDB / MySQL | 10.11 / 8.0 | `INSERT ... ON DUPLICATE KEY UPDATE` or a transaction for multi-table writes |
| pawncc | 3.10.10+ | `-d3` so a callback crash prints a usable trace |

`mysql_query` exists in R41 and is synchronous: it blocks the tick until the server answers. Treat it as forbidden on the main thread; the only acceptable calls are `mysql_tquery` (queued, ordered) and `mysql_pquery` (parallel, unordered).

## Production Implementation
1. Model the session as a state (`DATA_FREE / LOADING / READY / SAVING`) and gate every write on `READY`.
2. Load in `OnPlayerConnect` with `mysql_tquery` and a callback name plus an argument format.
3. Stamp a session counter on each load and drop replies whose counter no longer matches — that is what a fast reconnect breaks.
4. Read the primary key with the data, so saves never need the player name again.
5. Mark dirty on change and flush from a `ptask`; capture the numbers as timer parameters so a reused slot cannot write someone else's row.
6. On disconnect issue `mysql_pquery` with the captured values and never wait for it.

```pawn
#include <a_mysql>
#include <YSI_Coding\y_timers>

enum E_DATA_STATE
{
    DATA_FREE = 0,
    DATA_LOADING,
    DATA_READY,
    DATA_SAVING
};

new E_DATA_STATE:gDataState[MAX_PLAYERS];
new MySQL:gDB, gSession[MAX_PLAYERS];
new gDbId[MAX_PLAYERS];
new gMoney[MAX_PLAYERS], gLevel[MAX_PLAYERS];
new bool:gDirty[MAX_PLAYERS];
new gNameEsc[MAX_PLAYERS][(MAX_PLAYER_NAME * 2) + 2], gQuery[512];

forward OnDataLoaded(playerid, session);

stock LoadPlayerData(playerid)
{
    new name[MAX_PLAYER_NAME + 1];
    GetPlayerName(playerid, name, sizeof name);
    mysql_escape_string(name, gNameEsc[playerid]);   // never interpolate a raw name

    gDataState[playerid] = DATA_LOADING;
    mysql_format(gDB, gQuery, sizeof gQuery,
        "SELECT id, money, level FROM players WHERE name = '%s' LIMIT 1",
        gNameEsc[playerid]);
    mysql_tquery(gDB, gQuery, "OnDataLoaded", "ii", playerid, ++gSession[playerid]);
    return 1;
}

public OnDataLoaded(playerid, session)
{
    if (!IsPlayerConnected(playerid)) return 1;                 // slot already gone
    if (session != gSession[playerid]) return 1;                // reply from an older connection

    if (!cache_num_rows())                                      // first login: create the row
    {
        mysql_format(gDB, gQuery, sizeof gQuery,
            "INSERT INTO players (name, money, level) VALUES ('%s', 500, 1)",
            gNameEsc[playerid]);
        mysql_tquery(gDB, gQuery, "OnDataCreated", "i", playerid);
        return 1;                                   // the state flips in the insert callback
    }

    cache_get_value_name_int(0, "id", gDbId[playerid]);
    cache_get_value_name_int(0, "money", gMoney[playerid]);
    cache_get_value_name_int(0, "level", gLevel[playerid]);

    gDataState[playerid] = DATA_READY;
    printf("[data] ready p=%d id=%d source=load", playerid, gDbId[playerid]);
    return 1;
}

public OnDataCreated(playerid)
{
    if (!IsPlayerConnected(playerid)) return 1;
    gDbId[playerid] = cache_insert_id();      // only valid inside this INSERT's callback
    gMoney[playerid] = 500;
    gLevel[playerid] = 1;
    gDataState[playerid] = DATA_READY;
    printf("[data] ready p=%d id=%d source=create", playerid, gDbId[playerid]);
    return 1;
}
```

`cache_num_rows()` is the stock wrapper around `cache_get_row_count(rows)` — the native takes the count by reference, so calling it as a value does not compile.

```pawn
timer FlushPlayerData[2000](playerid, dbid, money, level)
{
    if (!IsPlayerConnected(playerid)) return 1;   // session over, the disconnect path saved it

    mysql_format(gDB, gQuery, sizeof gQuery,
        "UPDATE players SET money = %d, level = %d WHERE id = %d", money, level, dbid);
    mysql_pquery(gDB, gQuery, "OnDataSaved", "i", playerid);
    return 1;
}

ptask FlushDirty[5000](playerid)                  // debounce: at most one save per 5 s
{
    if (!gDirty[playerid] || gDataState[playerid] != DATA_READY) return 1;
    if (mysql_unprocessed_queries(gDB) > 100) return 1;   // backpressure, retry next tick
    gDirty[playerid] = false;
    gDataState[playerid] = DATA_SAVING;
    defer FlushPlayerData(playerid, gDbId[playerid], gMoney[playerid], gLevel[playerid]);
    return 1;
}

public OnDataSaved(playerid)
{
    if (IsPlayerConnected(playerid) && gDataState[playerid] == DATA_SAVING)
        gDataState[playerid] = DATA_READY;
    return 1;
}
```

## Failure Modes & Fixes
| Symptom | Cause | Fix |
| --- | --- | --- |
| money resets after login | commands ran before `DATA_READY` | gate every write on the state, not on `IsPlayerConnected` |
| quick reconnect restores old data | a late callback from the previous session applied | compare the session counter in the callback |
| server freezes on quit | `mysql_query` in `OnPlayerDisconnect` | `mysql_pquery` with values captured before the slot frees |
| `error 035: argument type mismatch` on `cache_get_row_count` | called as a value | `cache_num_rows()`, or pass a variable by reference |
| save writes another player's money | `gMoney[playerid]` read after slot reuse | pass the numbers as timer parameters |
| `You have an error in your SQL syntax` on names with `'` | unescaped name | `mysql_escape_string` before `mysql_format` |
| query queue grows without bound | every change issues a save | debounce with `ptask` plus `mysql_unprocessed_queries` backpressure |
| load never completes | callback name typo | the name must match the `forward`ed public exactly, and the format must match the argument count |

## Verification
```bash
grep -rn "mysql_query(" gamemodes/ | grep -v "tquery\|pquery"
```
Expected: no output — no synchronous query left in the gamemode.

```bash
mysql -h127.0.0.1 -usamp -p"$DBPASS" samp -e "SELECT money FROM players WHERE name='Tester';"
```
Expected: the value you set in game is returned before and after a reconnect, e.g. `1234`. Then count the readiness lines: exactly one `[data] ready` per connection, and a second one for the same slot after a fast reconnect proves the stale-session guard failed.

```bash
grep -c "\[data\] ready" logs/server.log
```
Expected: equal to the number of connects in the same log.

## Sources (2026)
- [BlueG/SA-MP-MySQL](https://github.com/pBlueG/SA-MP-MySQL) — R41 API: `mysql_tquery`, `mysql_pquery`, `mysql_escape_string`, cache reads.
- [mysql.inc source](https://raw.githubusercontent.com/pBlueG/SA-MP-MySQL/master/a_mysql.inc.in) — exact native signatures, `cache_get_row_count(&destination)`, `cache_num_rows()`.
- [open.mp documentation](https://open.mp/docs) — component loading and the 2026 callback set.
