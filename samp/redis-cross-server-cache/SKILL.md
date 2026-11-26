---
name: redis-cross-server-cache
description: Use when two servers must share live state fast.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, cache, redis]
    category: samp
---

# Redis between servers: TTL'd keys, hashes and one pub/sub channel

## When to Use

- Two or more open.mp instances (lobby + gamemode, or a sharded world) must see the same bans, mute
  list or online count.
- Every join reads the same three rows from MySQL and the query log shows it.
- A ban applied on server A must take effect on server B within seconds, not on next restart.
- Redis is *not* the source of truth here; the SQL database stays authoritative.

## Compatibility & Stack Matrix (2026)

| Piece | Version / variant | Note |
| --- | --- | --- |
| Redis | 7.x | `SETEX`, `HSET`, `PUBLISH` are stable and unchanged |
| Pawn client | `Southclaws/pawn-redis` (`#include <redis>`) | natives `Redis_*`, one connection handle per server |
| Server | open.mp 1.4/1.5 or SA-MP 0.3.7-R5 | plugin is a legacy plugin: `pawn.legacy_plugins` |
| Network | private interface or unix socket tunnel | never expose 6379 to the internet |
| Key scope | `samp:<env>:<feature>:<id>` | one prefix per environment so staging cannot poison live |
| Eviction | `maxmemory-policy allkeys-lru` for a pure cache | a queue or ban store needs `noeviction` |

## Production Implementation

1. Give each key an owner and a TTL. A key without a TTL is a leak, and the Pawn native has no TTL
   argument, so expiry must go through `Redis_Command` with `SETEX`:

```pawn
#include <redis>

new Redis:g_Redis;

stock CachePublishOnline(serverid, const name[])
{
    new cmd[192];
    format(cmd, sizeof cmd, "SETEX samp:live:online:%d 45 \"%s\"", serverid, name);
    return Redis_Command(g_Redis, cmd);          // SETEX <key> <seconds> <value>
}
```

2. Use a hash for records that change field by field. `Redis_SetHString` maps to `HSET`, and reading
   one field is `Redis_GetHString` (`HGET`), so a ban list does not need a full re-read:

```pawn
stock CacheBan(playerid, const reason[])
{
    new cmd[256];
    format(cmd, sizeof cmd, "HSET samp:live:bans %d \"%s\"", playerid, reason);
    return Redis_Command(g_Redis, cmd);
}

stock bool:CacheIsBanned(playerid, dest[], size)
{
    new field[12];
    format(field, sizeof field, "%d", playerid);   // hash field is a string, not an int
    dest[0] = EOS;
    return Redis_GetHString(g_Redis, "samp:live:bans", field, dest, size) && dest[0];
}
```

3. Read-through with a fallback. A cache miss is a database read, not an error; a Redis outage must
   degrade latency, never correctness:

```pawn
stock LoadLevel(playerid)
{
    new buf[16], key[48];
    format(key, sizeof key, "samp:cache:level:%d", playerid);
    if (Redis_GetString(g_Redis, key, buf, sizeof buf) && buf[0]) return strval(buf);

    new level = SqlSelectLevel(playerid);        // authoritative read
    format(key, sizeof key, "SETEX samp:cache:level:%d 300 %d", playerid, level);
    Redis_Command(g_Redis, key);
    return level;
}
```

4. Notify peers with one channel per feature, never one channel per server. `PUBLISH` returns the
   number of subscribers that received the message, which is your health signal:

```pawn
stock AnnounceBan(playerid, const reason[])
{
    new payload[256];
    format(payload, sizeof payload, "BAN|%d|%s", playerid, reason);
    return Redis_Publish(g_Redis, "samp:events", payload);
}
```

5. Subscribe on boot with a callback that only queues work. The callback runs on the plugin's
   subscriber thread, so it must not touch player state directly:

```pawn
forward OnCacheEvent(channel[], data[]);
public OnCacheEvent(channel[], data[])
{
    if (strcmp(channel, "samp:events") != 0) return 1;
    // push to a queue drained by a timer on the main thread
    QueueRemoteEvent(data);
    return 1;
}

stock StartSubscriber()
{
    new PubSub:sub;
    return Redis_Subscribe("127.0.0.1", 6379, "", "samp:events", "OnCacheEvent", sub);
}
```

6. Invalidate instead of guessing TTLs on writes that must be visible immediately: `DEL` the key on
   the writer, then let the next reader repopulate it. For counters use `INCR`/`HINCRBY`, never
   read-modify-write from Pawn, because two servers will lose an update.

7. Name keys so a Redis Cluster deployment keeps related keys in one slot — anything inside `{}` is
   the hash tag: `samp:{eu1}:bans` and `samp:{eu1}:mutes` land together, `samp:{us1}:bans` does not.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Online count stuck after a crash | key written with `SET` and no expiry | always `SETEX`; 45 s is longer than a restart |
| Two servers both think they banned the player, list differs | each server kept its own copy | one `samp:live:bans` hash, `HSET` from any server |
| `Redis_GetString` returns empty for an existing key | key written by `Redis_SetInt` (different type) | keep one type per key, document it in the key table |
| Ban visible 5 minutes late | only TTL invalidation, no publish | `DEL` on write plus `PUBLISH samp:events` |
| Player state corrupted after a remote event | subscriber callback touched players off-thread | queue in the callback, apply on a main-thread timer |
| Money doubled during a Redis failover | economy cached with read-modify-write | economy stays in SQL with a transaction, Redis holds display only |

## Verification

```bash
redis-cli -h 127.0.0.1 --no-auth-warning SETEX samp:live:online:1 45 Ferz
redis-cli TTL samp:live:online:1
redis-cli HSET samp:live:bans 42 "speedhack 2026-11-01"
redis-cli HGETALL samp:live:bans
redis-cli PUBLISH samp:events "BAN|42|speedhack"
```

Expected output (`TTL` is the remaining seconds, `PUBLISH` the subscriber count — 2 with two servers):

```text
OK
44
(integer) 1
1) "42"
2) "speedhack 2026-11-01"
(integer) 2
```

- Manual: `redis-cli MONITOR` while one player connects shows `SETEX` then a `PUBLISH`; the second
  server's log shows the queued event within one second.
- Manual: stop Redis, join with the cache warm and cold — both must still load from SQL, with a
  logged warning and no crash.

## Sources (2026)

- https://github.com/Southclaws/pawn-redis — `redis.inc` natives used above (`Redis_Command`,
  `Redis_SetHString`, `Redis_Publish`, `Redis_Subscribe`).
- https://redis.io/docs/latest/commands/setex/ — `SETEX key seconds value` semantics and return.
- https://redis.io/docs/latest/develop/pubsub/ — channel delivery, no persistence for pub/sub messages.
