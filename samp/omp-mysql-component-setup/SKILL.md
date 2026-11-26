---
name: omp-mysql-component-setup
description: Use when a legacy MySQL plugin must become a component.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql, component, migration]
    category: samp
---

# Swap the MySQL plugin for the component, then keep every query async

open.mp discovers components by scanning `components/`, not by a config key, so the MySQL
component needs no `config.json` entry — but the old plugin entry must go, or two
implementations register the same result-reading natives and the first one wins.
`imshooter/MySQL` 0.3.1 runs one ordered connection per handle plus a `pool` for parallel
reads, and blocks only in `MySQL_Run`.

## When to Use

- You are moving a gamemode off the BlueG R41 plugin onto the compiled component.
- `config.json` still lists `mysql` under `pawn.legacy_plugins`.
- Saves hitch the tick because a query path calls a synchronous native.

## Compatibility & Stack Matrix (2026)

| Layer | 2026 baseline | Note |
| --- | --- | --- |
| Component | MySQL 0.3.1, `mysql.so` / `mysql.dll` | drop in `components/`; discovery is a folder scan, no key |
| Legacy entry | `pawn.legacy_plugins: ["mysql"]` | remove it, it is a read-only startup key |
| Include | `mysql.inc` → `qawno/include`, `#include <mysql>` | needs only open.mp natives; names do not collide with R41 |
| Runtime deps | MariaDB Connector/C 3.4.11, yyjson, Argon2, OpenSSL 3 | linked in, so no extra file and no plugin |
| Platform | 32-bit only | Linux wants glibc ≥ 2.28 and `libc6:i386` |
| Server | open.mp 1.6.x | `MySQL_Run` is the only call that waits for an answer |

## Production Implementation

1. Install the binary and delete the legacy path in the same change — the include may sit
   beside R41 while you migrate, but the plugin must not load:

```bash
test -f components/mysql.so && echo component-present
rm -f plugins/mysql.so
python3 -c "import json;c=json.load(open('config.json'));p=c.setdefault('pawn',{});p['legacy_plugins']=[x for x in p.get('legacy_plugins',[]) if 'mysql' not in x.lower()];json.dump(c,open('config.json','w'),indent=2);print('legacy_plugins:',p['legacy_plugins'])"
```

2. Put credentials in `mysql.ini` next to the server. `MySQL_ConnectFile` takes the R41 keys
   plus every option key (`hostname`, `username`, `password`, `database`, `server_port`,
   `pool_size`, `ssl_enable`, `ssl_ca_file`). A value written `${NAME}` comes from the server
   environment, and an unset variable invalidates the file rather than connecting empty:

```ini
hostname = 127.0.0.1
username = game
password = ${MYSQL_PASSWORD}
database = game
pool = 2
slow_query = 200
read_timeout = 10
max_pending = 64
```

3. Connect once and treat a bad file as fatal. A failed connection still returns a handle, so
   `INVALID_MYSQL_ID` means "settings are wrong" while `MySQL_IsConnected` false means "the
   database is not up yet" — the next query reconnects on its own:

```pawn
// declared by mysql.inc 0.3.1; repeated so the calls below read on their own
native MySQL:MySQL_ConnectFile(const file[]);
native bool:MySQL_IsConnected(MySQL:handle);
native MySQL_GetConnectionError(MySQL:handle, dest[]);
native MySQL_ThreadedQuery(MySQL:handle, const callback[], context, const format[], {Float,_}:...);
native MySQL_GetErrno();
native MySQL_GetRowCount();
native MySQL_GetValueInt(row, const field[], &value);

static MySQL:gDB = INVALID_MYSQL_ID;

stock DBInit()
{
    gDB = MySQL_ConnectFile("mysql.ini");
    if (gDB == INVALID_MYSQL_ID)
        return print("[db] mysql.ini is not valid"), 0;

    if (!MySQL_IsConnected(gDB))
    {
        new reason[128];
        MySQL_GetConnectionError(gDB, reason);
        printf("[db] not reachable yet: %s", reason);
    }
    return 1;
}
```

4. Route reads through `MySQL_ThreadedQuery` and forget-me writes through `MySQL_Send`. The
   public runs on a later server tick, never on the query thread, so natives are legal — but
   the player may already be gone:

```pawn
forward OnAccountLoaded(playerid);   // the context, not the SQL, identifies the caller

stock DBLoadAccount(playerid)
{
    new name[MAX_PLAYER_NAME + 1];
    GetPlayerName(playerid, name, sizeof name);
    MySQL_ThreadedQuery(gDB, "OnAccountLoaded", playerid,
        "SELECT cash, bank FROM accounts WHERE name = %q LIMIT 1", name);
    return 1;
}

public OnAccountLoaded(playerid)
{
    if (!IsPlayerConnected(playerid)) return 0;      // quit raced the query
    if (MySQL_GetErrno() != 0 || MySQL_GetRowCount() == 0)
    {
        SendClientMessage(playerid, 0xFF4444FF, "Account row missing.");
        return 0;
    }
    MySQL_GetValueInt(0, "cash", gCash[playerid]);
    MySQL_GetValueInt(0, "bank", gBank[playerid]);
    return 1;
}
```

5. Let the component format every statement: `%q` escapes and quotes a string, `%e` only
   escapes, `%s` writes raw text for table and column names the script chose — hand-built SQL
   with `format` is how a name with a quote becomes a syntax error at three in the morning.

6. Keep `MySQL_Run` for schema work in `OnGameModeInit`: it stops the server until the
   database answers and has no callback to escape into. Anything a player triggers is
   `MySQL_ThreadedQuery` (ordered) or `MySQL_ParallelQuery` (out of order, needs `pool > 0`).
   `max_queries_per_second` and `max_pending` refuse past their ceiling and log once a
   second, so a retry storm reads as a flat refusal rate instead of a growing queue.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Compile fails with "function is already defined" on `mysql_*` | legacy plugin still in `plugins/` or `pawn.legacy_plugins` | remove both, keep one implementation |
| Handle compares unequal to 0 yet every query fails | `INVALID_MYSQL_ID` is the component's null handle | compare against `INVALID_MYSQL_ID`, then `MySQL_IsConnected` |
| `MySQL_ConnectFile` invalid with a correct-looking file | unknown key, bad value, or unset `${VAR}` | read the logged reason, then the key names |
| Server freezes for a second on every save | `MySQL_Run` on a player path | move to `MySQL_ThreadedQuery` or `MySQL_Send` |
| Callback writes to a player who already left | public fired after quit | `IsPlayerConnected` as its first statement |
| Works for hours then refuses every query | `max_pending` or `max_queries_per_second` reached | batch writes, then raise the limit deliberately |

## Verification

```bash
grep -rnE "mysql_tquery|mysql_pquery|cache_get_field_content|mysql_connect\(" gamemodes/ ; echo "legacy_exit=$?"
grep -c "legacy_plugins.*mysql" config.json
grep -iE "loaded component mysql|mysql.ini is not valid" server_log.txt | tail -3
```

Expected on a clean migration — no legacy native, no plugin entry, component named once:

```text
legacy_exit=1
0
[Info] Loaded component mysql (0.3.1)
```

Then the behavioural check: one account load and one ban write, no `OnMySQLError` line, and
the `players` row updated on the next tick, not inside the event that triggered it.

## Sources (2026)

- https://github.com/imshooter/MySQL/wiki/Configuration — the `MySQL_Connect` option string, every key and default, `mysql.ini` keys, `${NAME}` expansion, reconnect backoff.
- https://github.com/imshooter/MySQL/wiki/Installation — files and folders, `INVALID_MYSQL_ID`, `MySQL_IsConnected`, build targets.
- https://open.mp/docs/server/config.json — `pawn.legacy_plugins` is a read-only startup key; components are discovered from the folder.
