---
name: transaction-rollback-economy
description: Use when money must move atomically or roll back.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql, transactions, economy]
    category: samp
---

# Move money in one statement batch, never across calls

A debit is only safe if the balance check, the debit and the ledger row commit
together. R41-4 pools connections and a transaction is session state on one
socket, so `START TRANSACTION` in one `mysql_tquery` and `COMMIT` in the next can
land on two connections. Use one guarded multi-statement batch per operation,
opened with `ROLLBACK;` so a failed batch cannot leak an open transaction.

## When to Use

- A purchase, transfer, job payout or fine must debit and record together.
- Money vanished or doubled after a timeout, a crash, or a reconnect.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.4.x (Pawn 1.6.7) or SA-MP 0.3.7 | same Pawn API for the batch |
| MySQL plugin | BlueG R41-4 (`mysql.so`) | `MULTI_STATEMENTS` defaults to false, `POOL_SIZE` to 2 |
| Database | MySQL 8.4 LTS / 8.0 | InnoDB required; MyISAM ignores `ROLLBACK` |
| Account auth | `mysql_native_password` for the gamemode account | the R41-4 build tested here returned `1045` on an 8.4 `caching_sha2_password` account |
| Money column | `BIGINT`, never `FLOAT`/`DOUBLE` | float drift reads as duplication |
| Isolation | InnoDB default `REPEATABLE READ` | row locks from `UPDATE` hold until `COMMIT` |

## Production Implementation

1. Integers for money, one ledger row per change, `UNIQUE(ref)` as the replay
   guard, `CHECK` so no code path can store a negative balance.

```sql
CREATE TABLE accounts (
  id    INT UNSIGNED NOT NULL PRIMARY KEY,
  name  VARCHAR(24)  NOT NULL,
  money BIGINT       NOT NULL DEFAULT 0,
  UNIQUE KEY accounts_name (name),
  CONSTRAINT accounts_money_nonneg CHECK (money >= 0)
) ENGINE=InnoDB;

CREATE TABLE economy_ledger (
  id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  account INT UNSIGNED NOT NULL,
  delta   BIGINT       NOT NULL,
  reason  VARCHAR(32)  NOT NULL,
  ref     CHAR(36)     NOT NULL,
  balance BIGINT       NOT NULL DEFAULT -1,   -- -1 = reserved, not yet stamped
  UNIQUE KEY ledger_ref (ref),
  KEY ledger_account (account, id),
  CONSTRAINT ledger_account_fk FOREIGN KEY (account) REFERENCES accounts(id)
) ENGINE=InnoDB;
```

2. One batch per operation: `@fresh` proves the `ref` is new, `@paid` records
   whether the guarded debit matched.

```sql
ROLLBACK;                                  -- clears a leaked transaction
START TRANSACTION;
INSERT INTO economy_ledger (account, delta, reason, ref, balance)
  VALUES (7, -250, 'purchase', 'ref-0001', -1)
  ON DUPLICATE KEY UPDATE ref = ref;       -- replay = 0 rows, no error
SET @fresh := ROW_COUNT();
UPDATE accounts SET money = money - 250
  WHERE id = 7 AND @fresh = 1 AND money >= 250;
SET @paid := ROW_COUNT();
UPDATE economy_ledger SET balance = (SELECT money FROM accounts WHERE id = 7)
  WHERE ref = 'ref-0001' AND @paid = 1;
DELETE FROM economy_ledger WHERE ref = 'ref-0001' AND balance = -1 AND @paid = 0;
COMMIT;
```

3. Enable multi-statements and pin the pool before connecting; the enum members
   are bare, not `MYSQL_OPTION_*`.

```pawn
public OnGameModeInit()
{
    new MySQLOpt:opt = mysql_init_options();
    mysql_set_option(opt, MULTI_STATEMENTS, true);   // batch support
    mysql_set_option(opt, POOL_SIZE, 1);             // one socket, one tx owner
    g_DB = mysql_connect("127.0.0.1", "samp", "samp", "samp", opt);
}
```

4. Escape every string with `%e`; `'%s'` around a player reason is injection.

```pawn
stock Econ_Debit(playerid, const ref[], amount, const reason[])
{
    if (amount <= 0 || amount > 999999999) return 0;
    new q[1024];
    mysql_format(g_DB, q, sizeof q,
        "ROLLBACK;\
         START TRANSACTION;\
         INSERT INTO economy_ledger (account, delta, reason, ref, balance) \
           VALUES (%d, -%d, '%e', '%e', -1) ON DUPLICATE KEY UPDATE ref = ref;\
         SET @fresh := ROW_COUNT();\
         UPDATE accounts SET money = money - %d \
           WHERE id = %d AND @fresh = 1 AND money >= %d;\
         SET @paid := ROW_COUNT();\
         UPDATE economy_ledger SET balance = (SELECT money FROM accounts WHERE id = %d) \
           WHERE ref = '%e' AND @paid = 1;\
         DELETE FROM economy_ledger WHERE ref = '%e' AND balance = -1 AND @paid = 0;\
         COMMIT",
        g_Account[playerid], amount, reason, ref, amount,
        g_Account[playerid], amount, g_Account[playerid], ref, ref);
    return mysql_tquery(g_DB, q, "OnEconDebit", "dsd", playerid, ref, amount);
}
```

5. A failed batch fires neither its callback nor `OnQueryError` in R41-4; the
   transaction stays open on that socket. Read the outcome from the ledger and
   treat "no callback" as failure.

```pawn
new rows, balance;
cache_get_row_count(rows);
if (rows == 0) return 0;                  // no funds, or rolled back
cache_get_value_name_int(0, "balance", balance);
g_Money[playerid] = balance;              // trust the committed row
```

6. Deadlock `1213` and lock wait timeout `1205` are normal under concurrent
   spending: lock rows in ascending `id` order and retry the whole batch once.

7. Reconcile from the ledger on a timer; an imported account needs an `opening`
   row with `delta = money` or it shows as permanent drift.

```sql
SELECT a.id, a.money, COALESCE(SUM(l.delta), 0) AS ledger_sum,
       a.money - COALESCE(SUM(l.delta), 0) AS drift
FROM accounts a LEFT JOIN economy_ledger l ON l.account = a.id
GROUP BY a.id, a.money
HAVING drift <> 0;
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Item granted, balance unchanged | `UPDATE` and ledger row sent as separate queries | one multi-statement batch ending in `COMMIT` |
| Same `ref` debits twice after a retry | funds checked in Pawn before the `UPDATE` | claim `ref` first, debit only when `@fresh = 1` |
| Random `1213` under load | two batches lock the same accounts in opposite order | ascending `id` order, retry the batch once |
| Unrelated query writes at the wrong balance | failed batch left an open transaction on the socket | `ROLLBACK;` first in every batch |

## Verification

```bash
mysql -h127.0.0.1 -uroot -p"$PW" samp --table -e "
  SELECT money FROM accounts WHERE id = 7;
  SELECT COUNT(*) AS rows_for_ref FROM economy_ledger WHERE ref = 'ref-0001';"
```

- One debit plus one replay: `money` falls 250 once, `rows_for_ref` is `1`.

## Sources (2026)

- https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html
- https://dev.mysql.com/doc/refman/8.4/en/innodb-deadlocks-handling.html
- https://github.com/pBlueG/SA-MP-MySQL
