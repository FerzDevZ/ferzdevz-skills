---
name: economy-inflation-analytics
description: Use when prices drift and nobody can prove why.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, economy, mysql, analytics]
    category: samp
---

# Measure inflation from ledger flows, not from account balances

A balance tells you who is rich, not whether the server printed money this week. Inflation
is a flow problem: every payout is a faucet, every purchase a sink, and their ratio over 7
to 30 days is what moves prices. Build the ledger once, classify every reason, roll it up
nightly, and read the rollup instead of scanning millions of raw rows.

## When to Use

- Prices drift and new players cannot reach the first purchase.
- Nobody can say how much money the server printed last week.
- A payout is buffed and the effect is measured by "feels richer".
- The report query takes seconds because it aggregates the raw ledger.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Note |
| --- | --- | --- |
| Store | InnoDB ledger, append-only | one row per money change, never updated |
| Engine | MySQL 8.4 LTS / MariaDB 10.11 | window functions available in both |
| Plugin | BlueG MySQL R41-4 (`a_mysql`) | async inserts only, never on the tick path |
| Rollup | `econ_daily` written once per day | the report reads this, not the ledger |
| Classification | `econ_reason.kind` = faucet / sink / transfer | transfers must be excluded from both sums |
| Spot check | `GetPlayerMoney` | confirms the ledger row matches the client HUD |
| Supply snapshot | `SUM(cash + bank)` over accounts | money supply at a point in time |

## Production Implementation

1. Create the ledger with the three indexes the reports need, and a dictionary table that
   classifies reasons once instead of in every query:

```sql
CREATE TABLE moneylog (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  account_id INT UNSIGNED NOT NULL,
  reason VARCHAR(32) NOT NULL,
  delta INT NOT NULL,
  balance_after BIGINT NOT NULL,
  PRIMARY KEY (id),
  KEY ml_ts (ts),
  KEY ml_reason_ts (reason, ts),
  KEY ml_account_ts (account_id, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE econ_reason (
  reason VARCHAR(32) NOT NULL,
  kind ENUM('faucet','sink','transfer') NOT NULL,
  PRIMARY KEY (reason)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO econ_reason (reason, kind) VALUES
  ('job_payout','faucet'), ('bank_interest','faucet'), ('admin_give','faucet'),
  ('shop_buy','sink'), ('vehicle_buy','sink'), ('fine','sink'), ('player_transfer','transfer');
```

2. Write through one function, after the money has changed, so `balance_after` is the
   result and not the intent. A signed `delta` is what makes the sink side add up:

```pawn
// a_mysql.inc provides mysql_format, mysql_escape_string and mysql_tquery
stock EconLog(playerid, const reason[], delta)
{
    new query[256], escaped[48];
    mysql_escape_string(reason, escaped, sizeof escaped, gDB);   // name, never SQL
    mysql_format(gDB, query, sizeof query,
        "INSERT INTO moneylog (account_id, reason, delta, balance_after) VALUES (%d, '%s', %d, %d)",
        gAccount[playerid], escaped, delta, GetPlayerMoney(playerid));
    mysql_tquery(gDB, query, "", "");
    return 1;
}
```

3. Roll the previous day up once, at 00:05 server time, with an upsert so a rerun after a
   restart does not duplicate the row. `VALUES()` refers to the row that would have been
   inserted:

```sql
INSERT INTO econ_daily (day, faucet, sink, players)
SELECT DATE(m.ts),
       SUM(CASE WHEN r.kind = 'faucet' THEN m.delta ELSE 0 END) AS faucet,
       SUM(CASE WHEN r.kind = 'sink'   THEN -m.delta ELSE 0 END) AS sink,
       COUNT(DISTINCT m.account_id) AS players
FROM moneylog m JOIN econ_reason r ON r.reason = m.reason
WHERE m.ts >= CURDATE() - INTERVAL 1 DAY
  AND m.ts <  CURDATE()
  AND r.kind <> 'transfer'
GROUP BY DATE(m.ts)
ON DUPLICATE KEY UPDATE faucet = VALUES(faucet), sink = VALUES(sink), players = VALUES(players);
```

4. Read the ratio with a running total, so a single loud day does not look like a trend.
   `NULLIF` keeps a sink-free day from turning into a division error:

```sql
SELECT day, faucet, sink,
       ROUND(faucet / NULLIF(sink, 0), 2) AS ratio,
       SUM(faucet - sink) OVER (ORDER BY day ROWS 6 PRECEDING) AS net_7d
FROM econ_daily
WHERE day >= CURDATE() - INTERVAL 30 DAY
ORDER BY day DESC;
```

5. Snapshot supply per player — fixed prices inflate when supply per player rises:

```sql
INSERT INTO econ_supply (day, accounts, supply, per_player)
SELECT CURDATE(), COUNT(*), SUM(cash + bank), ROUND(SUM(cash + bank) / NULLIF(COUNT(*), 0), 0)
FROM accounts
ON DUPLICATE KEY UPDATE supply = VALUES(supply), per_player = VALUES(per_player);
```

6. Expose it from the rollup, never from the ledger: `/econ` prints the last seven
   `econ_daily` rows. `ratio > 1.30` is faucet-heavy, `ratio < 0.90` is sink-heavy.

7. Tune one side at a time and wait for the 7-day net before the next change; a payout buff
   and a price cut landing in the same week cannot be told apart afterwards.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Faucet and sink both include the same money | `player_transfer` counted on both sides | filter `kind <> 'transfer'` |
| Report takes seconds and stalls the server | aggregation over the raw ledger from Pawn | read `econ_daily`, write it in SQL |
| Sink sums come out positive | purchases stored unsigned | store signed deltas, negate at aggregate |
| Ledger total disagrees with in-game money | a path calls `GivePlayerMoney` without `EconLog` | grep the money natives, route them |
| Ratio jumps at midnight | day boundary in UTC while players live in another zone | pin the session timezone in `my.cnf` |
| Duplicate rows after a restart | rollup ran twice with plain `INSERT` | keep the `ON DUPLICATE KEY UPDATE` |
| `balance_after` off by one change | logged before the money moved | log after `GivePlayerMoney` |

## Verification

The two sides of the ledger must have opposite signs and a defensible ratio:

```bash
mysql -uroot -p"$PW" samp -e "
SELECT r.kind, COUNT(*) rows_, SUM(m.delta) total
FROM moneylog m JOIN econ_reason r ON r.reason = m.reason
WHERE m.ts >= CURDATE() - INTERVAL 1 DAY AND r.kind <> 'transfer'
GROUP BY r.kind;"
```

Expected on a live server:

```text
+--------+-------+---------+
| faucet |  1842 | 1240500 |
| sink   |  5510 | -807300 |
+--------+-------+---------+
```

`faucet` positive, `sink` negative, ratio `1240500 / 807300 = 1.54`: faucet-heavy, prices
are about to drift. Both totals sharing a sign means the transfer filter or delta sign is
wrong, not the economy.

## Sources (2026)

- https://mariadb.com/docs/server/reference/sql-functions/aggregate-functions — `SUM`, `COUNT(DISTINCT)` and `GROUP BY` semantics used by the rollup.
- https://mariadb.com/docs/server/reference/sql-functions/special-functions/window-functions/window-functions-overview — `OVER (...) ROWS 6 PRECEDING` for the 7-day net.
- https://mariadb.com/docs/server/reference/sql-statements/data-manipulation/inserting-loading-data/insert-on-duplicate-key-update — upsert semantics and `VALUES()` in the update list.
