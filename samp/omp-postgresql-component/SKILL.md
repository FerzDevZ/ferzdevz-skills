---
name: omp-postgresql-component
description: Use when PostgreSQL must run async inside open.mp.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, database, postgres, async]
    category: samp
---

# PostgreSQL as a component: submit a job, answer in a tick

## When to Use

- The project standardises on PostgreSQL and you refuse the legacy threaded MySQL plugin.
- A query must never block the tick, including `OnPlayerConnect` and the money path.
- You are porting a BlueG `mysql_*` callback chain and need the component equivalent.
- Not for schema layout or migration order; that is `database-schema-migration`.

## Compatibility & Stack Matrix (2026)

| Piece | Version / variant | Note |
| --- | --- | --- |
| Component | `itskoleban/omp-postgresql` (C++20, libpq) | `PostgreSQL.so` goes in `components/`, not `plugins/` |
| Server | open.mp 1.5.8.3079 x86 | an x64 binary cannot load into an x86 server |
| Connection config | libpq service file + `PGPASSFILE` | read on the worker from the server's environment |
| API model | fully asynchronous | native returns immediately; results arrive in `OnPgComplete` |

## Production Implementation

1. Keep credentials out of Pawn. libpq reads the service profile and the password file from the server
   process environment, set before `omp-server` starts:

```bash
install -m 600 examples/pg_service.conf /srv/openmp-private/pg_service.conf
install -m 600 examples/pgpass /srv/openmp-private/pgpass
export PGSERVICEFILE=/srv/openmp-private/pg_service.conf PGPASSFILE=/srv/openmp-private/pgpass
./omp-server
```

2. Request the connection in `OnGameModeInit`. A nonzero handle means accepted locally, not authenticated:

```pawn
#include <open.mp>
#include <omp_postgresql>

new g_DB = PG_INVALID;

public OnGameModeInit()
{
    g_DB = pg_connect("game");          // pg_connect(profile, pool_size = 1)
    if (g_DB == PG_INVALID)
    {
        new err[256];
        pg_last_error(err);             // read immediately: the next native clears it
        printf("[pg] connect rejected: %s", err);
        return 0;
    }
    return 1;
}
```

3. Gate every submission on `PG_CONNECTED`. A failed or dropped connection invalidates the handle and
   must be closed; a later query on it fails locally instead of reconnecting:

```pawn
public OnPgConnection(connection, connection_state)
{
    if (connection != g_DB) return 1;
    if (connection_state == PG_CONNECTED) return print("[pg] pool ready");
    if (connection_state == PG_CONNECTION_FAILED || connection_state == PG_DISCONNECTED)
    {
        pg_connection_close(connection);   // handle is dead after this
        g_DB = PG_INVALID;
    }
    return 1;
}
```

4. Prepare once, bind per player. Indices start at 1, `pg_add` fixes the snapshot, untrusted text never
   enters the SQL string:

```pawn
new g_StmtLoad = 0;

stock LoadAccount(playerid, const name[])
{
    if (g_DB == PG_INVALID) return 0;
    if (!g_StmtLoad) g_StmtLoad = pg_prepare(g_DB,
        "SELECT money, level, pos_x FROM players WHERE username = $1", 1);
    if (!g_StmtLoad) return 0;
    if (!pg_bind_string(g_StmtLoad, 1, name) || !pg_add(g_StmtLoad)) return 0;
    return pg_execute(g_StmtLoad, .lane = 0, .transaction = 0, .context = playerid);
}
```

5. Read the result only after checking the terminal status and the shape. `context` carries the player
   id back, so no global "current player" variable is needed:

```pawn
public OnPgComplete(job, context)
{
    if (pg_job_status(job) != PG_CONFIRMED)
    {
        printf("[pg] job %d player %d ended %d error %d",
            job, context, pg_job_status(job), pg_job_error(job));
        pg_job_close(job);
        return 0;
    }
    new money, level, Float:px;
    if (pg_result_rows(job) == 1
        && pg_result_int(job, 0, 0, 0, money)
        && pg_result_int(job, 0, 0, 1, level)
        && pg_result_float(job, 0, 0, 2, px))
    {
        GivePlayerMoney(context, money);
        SetPlayerScore(context, level);
    }
    else Kick(context);         // no such account: kick, never invent defaults
    pg_job_close(job);          // releases the job and its retained results
    return 1;
}
```

6. Close in this order at shutdown: stop submitting, close the connection, let callbacks drain;
   `pg_connection_close` starts shutdown but does not prove a final save committed.

```pawn
public OnGameModeExit()
{
    if (g_DB != PG_INVALID) pg_connection_close(g_DB);
    g_DB = PG_INVALID;
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `connect rejected` immediately, no network error | `PGSERVICEFILE`/`PGPASSFILE` missing from the server environment | export both in the unit file, restart the process |
| `PG_CONNECTION_FAILED` with an auth message | `.pgpass` is not 0600 or the tuple does not match `host:port:db:user:pass` | fix permissions and the exact tuple |
| Gameplay reads zero values | result used before `OnPgComplete`, or a getter return ignored | gate on `PG_CONFIRMED`, check every `pg_result_*` boolean |
| Memory grows with player churn | `pg_job_close` skipped on the failure path | close in every branch of `OnPgComplete` |
| Component skipped at boot | binary from another release, or wrong architecture | match release and x86 |

## Verification

```bash
pawncc examples/basic.pwn -E -iqawno/include -i"$HOME/omp-stdlib" -obuild/basic.amx
grep -c "PG BASIC PASS" server/log.txt
```

Expected: a clean compile (no `Error:` lines), the component in the boot log, and a count of 1:

```text
[Info] Loading component PostgreSQL.so
PG BASIC PASS
1
```

- Manual: `systemctl stop postgresql` while running must log a disconnect, set `PG_INVALID`, and not stall.

## Sources (2026)

- https://github.com/itskoleban/omp-postgresql — component repository, install layout and limits.
- https://github.com/itskoleban/omp-postgresql/blob/master/docs/getting-started.md — `pg_connect`, `OnPgConnection`, `OnPgComplete`, result getters.
- https://www.postgresql.org/docs/17/libpq-pgservice.html — service file and password file semantics.
