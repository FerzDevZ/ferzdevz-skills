---
name: omp-postgresql-component
description: Use an async PostgreSQL component, verified not assumed.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, database, postgres]
    category: samp
---

# PostgreSQL component

## When to Use

- The project standardises on PostgreSQL instead of MySQL.
- You need async queries without the legacy threaded plugin model.

## 2026 Compatibility & Architecture Matrix

| Option | State (2026) | Note |
| --- | --- | --- |
| `omp-postgresql` (community) | async component, active | verify exported natives before designing around it |
| `omp-MySQL` (Mac-Andreas) | component, TLS + prepared statements | if you stay on MySQL |
| BlueG MySQL R41-4 | legacy plugin | still works, threaded API, no component interface |

## Production Implementation

1. Pin the include and enumerate the API you actually have:

```bash
grep -oE "native [A-Za-z_][A-Za-z0-9_]*" qawno/include/omp-postgresql.inc | sort -u
```

Do not write queries against function names from a blog post; the list above is the
contract.

2. Open one pool per process, not per query:

```pawn
new PG:g_DB;

public OnGameModeInit()
{
    g_DB = pg_connect("host=127.0.0.1 dbname=samp user=samp password=${PG_PASS}");
    if (g_DB == PG_INVALID) {
        print("postgres: connect failed - refusing to start");
        SendRconCommand("exit");
        return 0;
    }
    return 1;
}
```

3. Query asynchronously and keep the callback small:

```pawn
pg_query(g_DB, "SELECT id, name FROM players WHERE id = $1", playerid, "OnPlayerRow");
```

4. Keep schema parity with the MySQL path: same table names, same column types, and a
   migration file per change (`database-schema-migration`).

## Deprecated Traps & Edge Cases (2026)

- Assuming a component exists because a fork mentions it: confirm the release binary and
  the include for your platform.
- Blocking the main thread with a synchronous query inside `OnPlayerConnect`.
- `$1` placeholders with string interpolation instead of parameters: SQL injection returns.
- Timestamps: PostgreSQL `timestamptz` versus MySQL `DATETIME` silently shifts time zones.

## Verification

- `grep -c native` on the include matches the functions you call.
- A connect + insert + select round trip succeeds and is logged with latency.
- Stopping the DB makes the server log a clear failure, not a crash.

## Sources (2026)

- https://github.com/itskoleban/omp-postgresql
- https://github.com/Mac-Andreas/omp-MySQL
- https://github.com/Mac-Andreas/omp-MySQL/wiki
