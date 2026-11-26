---
name: mission-quest-objective-tracker
description: Use when quest steps complete out of order or reset.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, quests, persistence, mysql]
    category: samp
---

# Advance a quest only on the step's own event, and save on every advance

Quest bugs are ordering bugs: the kill counter fires while the player is still on "talk to
the dealer", the delivery completes before the package exists, and the step in memory is the
only copy of the truth. Fix it with a definition table and one function that is the only
writer of the step.

## When to Use

- Objectives complete out of order, or all at once.
- Progress is lost on reconnect, crash or gamemode restart.
- One action credits a step twice.
- A quest is stuck at step 0 for players who finished step 1 earlier.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 / SA-MP 0.3.7-R2 | one checkpoint per player |
| Database | MySQL 8.4 / MariaDB 10.11 | upsert keyed `(account_id, quest_id)` |
| Plugin | BlueG MySQL R41-4 (`a_mysql`) | `mysql_tquery` only, never on the tick path |
| State | quest id, step, counter per player | server authoritative, never client-reported |
| Checkpoint | `OnPlayerEnterCheckpoint` | disable before crediting: one entry, one credit |

## Production Implementation

1. Put the definitions in one table; a step is an event, a target count and a place, so every
   trigger validates against the same row:

```pawn
#include <openmp>
#include <a_mysql>            // mysql_format, mysql_tquery, cache_get_value_name_int
#define MAX_QUESTS (32)
#define MAX_STEPS (8)
#define QUEST_EVENT_KILL (1)
#define QUEST_EVENT_DELIVER (2)
#define QUEST_EVENT_REACH (3)

enum E_QuestStep { qsEvent, qsTarget, Float:qsX, Float:qsY, Float:qsZ };

new gQuestDef[MAX_QUESTS][MAX_STEPS][E_QuestStep];
new gQuestStepCount[MAX_QUESTS];
new gQuestCount;
new gQuestId[MAX_PLAYERS] = { -1, ... };
new gQuestStep[MAX_PLAYERS];
new gQuestDone[MAX_PLAYERS];
new bool:gQuestLoaded[MAX_PLAYERS];
```
2. Make one function the only writer of `gQuestStep`. It refuses an event that does not
   belong to the current step — out-of-order completion becomes impossible, not unlikely —
   and zeroes the counter, because a counter belongs to one step:

```pawn
stock QuestFire(playerid, event, amount = 1)
{
    if (!gQuestLoaded[playerid]) return 0;              // progress not read yet
    new q = gQuestId[playerid];
    if (q < 0 || q >= gQuestCount) return 0;
    new step = gQuestStep[playerid];
    if (step >= gQuestStepCount[q]) return 0;           // quest already finished
    if (gQuestDef[q][step][qsEvent] != event) return 0;

    gQuestDone[playerid] += amount;
    if (gQuestDone[playerid] < gQuestDef[q][step][qsTarget]) return 1;
    gQuestStep[playerid]++;  gQuestDone[playerid] = 0;
    QuestSave(playerid);
    QuestPlaceCheckpoint(playerid);
    return 1;
}

stock QuestPlaceCheckpoint(playerid)
{
    DisablePlayerCheckpoint(playerid);
    new q = gQuestId[playerid], step = gQuestStep[playerid];
    if (q < 0 || step >= gQuestStepCount[q]) return 0;   // finished or no quest
    return SetPlayerCheckpoint(playerid, gQuestDef[q][step][qsX], gQuestDef[q][step][qsY],
                               gQuestDef[q][step][qsZ], 3.0);
}
```
3. Persist with an upsert keyed on account and quest, so a relog, a crash or a duplicate
   callback collapse into one row:
```pawn
stock QuestSave(playerid)
{
    new query[256];
    mysql_format(gDB, query, sizeof query,
        "INSERT INTO quest_progress (account_id, quest_id, step, counter) VALUES (%d, %d, %d, %d) "
        "ON DUPLICATE KEY UPDATE step = VALUES(step), counter = VALUES(counter)",
        gAccount[playerid], gQuestId[playerid], gQuestStep[playerid], gQuestDone[playerid]);
    mysql_tquery(gDB, query, "", "");
    return 1;
}
```
4. Restore before accepting anything. The gate flag is set last, so a kill that lands between
   connect and load is dropped rather than overwriting the saved step:
```pawn
public OnQuestLoaded(playerid)
{
    if (!IsPlayerConnected(playerid)) return 0;
    new rows;  cache_get_row_count(rows);
    if (rows > 0)          // 0 rows: first visit, gQuestId stays -1
    {
        cache_get_value_name_int(0, "quest_id", gQuestId[playerid]);
        cache_get_value_name_int(0, "step", gQuestStep[playerid]);
        cache_get_value_name_int(0, "counter", gQuestDone[playerid]);
    }
    gQuestLoaded[playerid] = true;                       // gate opens last
    QuestPlaceCheckpoint(playerid);
    return 1;
}
```
5. Route world events into `QuestFire`: kills call it with `QUEST_EVENT_KILL`, delivery with
   `QUEST_EVENT_DELIVER`, checkpoints with `REACH`. No handler touches `gQuestStep` directly.
6. Credit a checkpoint once by disabling it before the call, because the callback can arrive
   twice for one arrival when a player re-enters while the checkpoint is still set:

```pawn
public OnPlayerEnterCheckpoint(playerid)
{
    DisablePlayerCheckpoint(playerid);
    QuestFire(playerid, QUEST_EVENT_REACH);
    return 1;
}
```
7. Key progress on `account_id`, not the player slot: `PRIMARY KEY (account_id, quest_id)` makes the upsert collide rather than append.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Steps complete out of order | handler incremented the step directly | only `QuestFire` advances, and it checks `qsEvent` |
| Progress lost on relog | saved only on disconnect | `QuestSave` on every advance |
| One kill credits two steps | step incremented before the counter reset | reset the counter in the same branch |
| Quest restarts at step 0 | event arrived before the load callback | `gQuestLoaded` gate, set last |
| Two players share progress | keyed on player id | primary key `(account_id, quest_id)` |
| Checkpoint gone after the first entry | disabled and never re-set | re-place after each advance |

## Verification

No row may hold a step outside its own definition, and no handler may write the step:

```bash
mysql -uroot -p"$PW" samp -e "SELECT account_id, quest_id, step FROM quest_progress WHERE step > 7;"
grep -rn "gQuestStep\[playerid\] *=" gamemodes/ | grep -v "quest.pwn"; echo "writers_exit=$?"
```

Expected — the `SELECT` prints an empty set:

```text
writers_exit=1
```

In game, complete step 1, relog and re-enter the door: `/quest` prints the saved step.

## Sources (2026)

- https://open.mp/docs/scripting/callbacks/OnPlayerEnterCheckpoint — one checkpoint per player, callback semantics.
- https://mariadb.com/docs/server/reference/sql-statements/data-manipulation/inserting-loading-data/insert-on-duplicate-key-update — upsert semantics and `VALUES()` in the update list.
- https://open.mp/docs/scripting/callbacks/OnPlayerDisconnect — disconnect reasons, and why saving only here loses a crash.
