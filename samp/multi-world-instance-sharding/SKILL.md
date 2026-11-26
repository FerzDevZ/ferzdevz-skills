---
name: multi-world-instance-sharding
description: Use when players must be split across worlds or servers.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, scaling, virtual-worlds, sharding]
    category: samp
---

# Shard by virtual world inside one server, by row affinity across servers

Virtual worlds hide players, vehicles and objects from each other; they do not
hide chat, money, or a shared scoreboard, and they do not partition a database.
Decide first which one you need: an instance on the same server (assign a world
range, route every teleport through one function) or a separate server (partition
accounts by a `shard` column and migrate players deliberately). Mixing the two
without an allocation map is how two shards end up writing the same account row.

## When to Use

- Two events must run at the same time on one map without seeing each other.
- A test or staff instance must share the code but not the players.
- One process cannot hold the population any more and you are adding a second server.
- Players report "ghosts" - a name or vehicle from another instance on screen.
- An account appears in two shards after a transfer and balances diverge.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | `SetPlayerVirtualWorld`, `SetVehicleVirtualWorld` verified |
| World id | 0 to 2,147,483,647 | the documented virtual-world limit; 0 is the default |
| Interiors | 256 total | interior ids are global, not per world |
| Visibility | players, vehicles, objects, labels | `SendClientMessageToAll` still crosses worlds |
| Streamer | 2.9.6, `worldid = -1` | `-1` means all worlds, which leaks an instance |
| Chat | per world via `foreach` | no native for world-scoped chat |
| Data | one DB, `accounts.shard` | worlds isolate nothing in SQL |

## Production Implementation

1. Reserve ranges instead of handing out loose numbers. A shard owns 1000 worlds;
   an instance inside it is a slot. Without a map, two features collide on world 5.

```pawn
#define WORLD_SHARD_BASE     1000     // each shard owns 1000 world ids
#define MAX_INSTANCE_SLOTS   1000
#define SHARD_MAIN           0
#define SHARD_EVENT          1

stock WorldOf(slot, shard = SHARD_MAIN)
{
    if (slot < 0 || slot >= MAX_INSTANCE_SLOTS) return 0;
    return shard * WORLD_SHARD_BASE + slot;
}
```

2. Route every teleport through one function. Setting the world after the
   position is the classic ghost bug: the position update reaches the old world
   before the new world is applied.

```pawn
stock EnterInstance(playerid, slot, interior, Float:x, Float:y, Float:z)
{
    SetPlayerVirtualWorld(playerid, WorldOf(slot));
    SetPlayerInterior(playerid, interior);          // 0-255, shared across worlds
    SetPlayerPos(playerid, x, y, z);
    SetTimerEx("ResyncPos", 50, false, "i", playerid); // re-send inside the new world
    return 1;
}

forward ResyncPos(playerid);
public ResyncPos(playerid)
{
    new Float:x, Float:y, Float:z;
    GetPlayerPos(playerid, x, y, z);
    Streamer_Update(playerid);              // rebuild the streamed set for this world
    SetPlayerPos(playerid, x, y, z);        // re-send so other clients place the player
}
```

3. Move vehicles with their driver. A car left in the old world is a ghost for
   everyone who stays behind, and an invisible driver for the ones who leave.

```pawn
stock EnterInstanceInVehicle(playerid, slot, interior, Float:x, Float:y, Float:z)
{
    new veh = GetPlayerVehicleID(playerid);
    SetVehicleVirtualWorld(veh, WorldOf(slot));
    SetPlayerVirtualWorld(playerid, WorldOf(slot));
    SetPlayerInterior(playerid, interior);
    SetVehiclePos(veh, x, y, z);
    return 1;
}
```

4. Scope chat and announcements yourself. `SendClientMessageToAll` reaches every
   world, so an event broadcast leaks into the lobby.

```pawn
stock SendWorldMessage(world, colour, const text[])
{
    foreach (new i : Player) if (GetPlayerVirtualWorld(i) == world)
        SendClientMessage(i, colour, text);
    return 1;
}
```

5. Never create a streamed object with `worldid` left at the default for an
   instance. Pass the world explicitly; `-1` is "all worlds" and shows the
   object in every instance at once.

6. For a second server, partition by account, not by session. Login reads
   `accounts.shard`; a player who belongs to shard 1 is refused on shard 0.

```sql
ALTER TABLE accounts ADD COLUMN shard TINYINT UNSIGNED NOT NULL DEFAULT 0;
SELECT shard FROM accounts WHERE name = ?;
```

7. Transfer an account with a conditional update while it is offline. The
   affected-row count tells you whether someone else moved it first.

```sql
UPDATE accounts SET shard = 1 WHERE id = ? AND shard = 0 AND online = 0;
-- affected_rows = 1 means this server won the move; 0 means re-read and retry
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Player sees the event instance for one frame | position set before the world | set world, then position, then resync after 50 ms |
| A car parked in the lobby appears inside the event | vehicle world never changed | `SetVehicleVirtualWorld` together with the player |
| Announcement appears in every instance | `SendClientMessageToAll` | world-scoped loop over `foreach (new i : Player)` |
| Object visible in all shards | streamer `worldid` left at `-1` | pass the instance world explicitly |
| Balance changed twice after a transfer | both servers wrote the row | conditional `UPDATE ... AND online = 0`, check affected rows |
| Interior walls missing in the event world | interior id reused across shards | interiors are global, 0-255; allocate them per shard |

## Verification

```bash
grep -rn "SetPlayerVirtualWorld" gamemodes/ | grep -v EnterInstance
mysql samp -e "SELECT shard, COUNT(*) FROM accounts GROUP BY shard;"
```

- The `grep` prints no hits: every world change goes through `EnterInstance`, so
  no teleport can skip the resync.
- The SQL result has one row per shard with no `NULL` shard, which is the
  partition contract the login code relies on.
- In game, two test accounts in slots 0 and 1: `GetPlayerVirtualWorld` returns
  0 and 1, neither can see the other's vehicle, and a world message sent to slot
  0 never reaches slot 1.

## Sources (2026)

- https://open.mp/docs/scripting/resources/limits
- https://open.mp/docs/scripting/functions/SetPlayerVirtualWorld
- https://open.mp/docs/scripting/functions/SetVehicleVirtualWorld
