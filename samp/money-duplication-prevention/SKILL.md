---
name: money-duplication-prevention
description: Use when balances grow with no matching ledger row.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql, economy, audit]
    category: samp
---

# One writer, one integer, one unique reference per change

Money duplication is rarely a clever exploit. It is a second code path writing
`PlayerData[money]`, a timer that pays twice, a save that writes a stale snapshot
over a newer balance, or a web panel that credits without a ledger row. Close all
four with structure: one writer function, integer storage with a hard cap, and one
unique reference per change that the database refuses twice.

## When to Use

- A balance grows with no matching job, trade, payout or admin action.
- Jobs, admin commands and a web UCP all write the same balance.
- A payout lands twice after a crash or a gamemode restart.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.4.x (Pawn 1.6.7) or SA-MP 0.3.7 | Pawn cells are 32-bit signed |
| Plugin | BlueG R41-4 | `cache_get_value_name_int` reads into a 32-bit cell |
| Database | MySQL 8.4 LTS / 8.0 | `BIGINT` column, `CHECK` cap enforced since 8.0.16 |
| Cap | `999999999` | the money HUD tops out here; anything above is invisible |
| Idempotency | `UNIQUE (ref)` on the ledger | the only guard that survives a retry |
| Writers | one Pawn function, one SQL shape | the web UCP uses the same shape |
| Audit | drift query on a timer | drift means a write happened outside the writer |

## Production Implementation

1. Bound the column at both ends: negative is a bug, above the cap is invisible.

```sql
CREATE TABLE accounts (
  id        INT UNSIGNED NOT NULL PRIMARY KEY,
  name      VARCHAR(24)  NOT NULL,
  money     BIGINT       NOT NULL DEFAULT 0,
  version   INT UNSIGNED NOT NULL DEFAULT 1,      -- optimistic save guard
  UNIQUE KEY accounts_name (name),
  CONSTRAINT accounts_money_range CHECK (money BETWEEN 0 AND 999999999)
) ENGINE=InnoDB;
```

2. Record every change with a unique `ref`; the database, not Pawn, decides whether
   a reference was already used. An imported balance needs one `opening` row, or
   reconciliation reports it as drift forever.

```sql
CREATE TABLE money_ledger (
  id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  account INT UNSIGNED NOT NULL,
  delta   BIGINT       NOT NULL,
  reason  VARCHAR(32)  NOT NULL,
  ref     CHAR(36)     NOT NULL,
  balance BIGINT       NOT NULL DEFAULT -1,   -- -1 = reserved, not yet applied
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY ledger_ref (ref),
  KEY ledger_account (account, id),
  CONSTRAINT ledger_account_fk FOREIGN KEY (account) REFERENCES accounts(id)
) ENGINE=InnoDB;
```

3. Route every write through one function; once a second script writes the
   balance, no audit can tell a bug from a feature.

```pawn
stock bool:AddMoney(playerid, delta, const reason[], const ref[])
{
    if (delta == 0 || ref[0] == EOS) return false;
    if (delta > 0 && g_Money[playerid] + delta > 999999999) return false;
    if (delta < 0 && g_Money[playerid] + delta < 0) return false;
    return Econ_Apply(playerid, delta, reason, ref);   // the batch from step 4
}
```

4. Credit is a guarded increment with the ledger claim in the same batch, so the
   cap and the replay check are decided by one transaction, not by Pawn.

```sql
ROLLBACK;
START TRANSACTION;
INSERT INTO money_ledger (account, delta, reason, ref, balance)
  VALUES (7, 500, 'job', 'job-7-1', -1)
  ON DUPLICATE KEY UPDATE ref = ref;
SET @fresh := ROW_COUNT();
UPDATE accounts SET money = money + 500, version = version + 1
  WHERE id = 7 AND @fresh = 1 AND money + 500 <= 999999999;
SET @paid := ROW_COUNT();
UPDATE money_ledger SET balance = (SELECT money FROM accounts WHERE id = 7)
  WHERE ref = 'job-7-1' AND @paid = 1;
DELETE FROM money_ledger WHERE ref = 'job-7-1' AND balance = -1 AND @paid = 0;
COMMIT;
```

5. Build the reference from stable parts plus a counter, never from `random()` or
   the current tick alone: a retry must reuse the same string.

```pawn
new ref[36];
format(ref, sizeof ref, "%d-%d-%d", g_Account[playerid], gettime(), g_Seq++);
```

6. Make the save a compare-and-set, so a stale Pawn snapshot cannot overwrite a
   newer balance written while the player was saving.

```sql
UPDATE accounts
   SET money = 750, version = version + 1
 WHERE id = 7 AND version = 12;
-- ROW_COUNT() = 0 means someone else wrote first: reload, do not overwrite
```

7. Apply payouts by account id in SQL, not `if (IsPlayerConnected(playerid))`: a
   disconnect must not delete money nor pay twice on reconnect.

```pawn
if (!IsPlayerConnected(playerid)) return Econ_ApplyOffline(account_id, delta, reason, ref);
```

8. Alert on drift instead of waiting for a report: compare each balance to the sum
   of its ledger rows, and alert on any row returned.

```sql
SELECT a.id, a.money, COALESCE(SUM(l.delta), 0) AS ledger_sum,
       a.money - COALESCE(SUM(l.delta), 0) AS drift
FROM accounts a LEFT JOIN money_ledger l ON l.account = a.id
GROUP BY a.id, a.money
HAVING drift <> 0;
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Payout paid twice after a restart | timer replayed with no idempotency key | stable `ref` per payout, `UNIQUE` on it, retry reuses the same string |
| Balance jumps to a huge negative | cap exceeded and a signed 32-bit cell wrapped | `CHECK (money BETWEEN 0 AND 999999999)` plus a Pawn guard |
| Money reverts after a save | stale Pawn snapshot overwrote a newer row | `WHERE version = ?` and reload on `ROW_COUNT() = 0` |
| Payout lost on disconnect | write guarded by `IsPlayerConnected` | apply by account id in SQL |
| Two systems disagree about a balance | job script and UCP both write `money` | one writer function, UCP inserts the same ledger shape |

## Verification

```bash
mysql -uroot -p"$PW" samp --table -e "
  INSERT INTO money_ledger (account, delta, reason, ref) VALUES (7, 500, 'job', 'job-7-1');"
mysql -uroot -p"$PW" samp --table -e "
  SELECT COUNT(*) AS drifted FROM (
    SELECT a.id FROM accounts a LEFT JOIN money_ledger l ON l.account = a.id
    GROUP BY a.id, a.money HAVING a.money <> COALESCE(SUM(l.delta), 0)) x;"
```

- The second insert of `job-7-1` fails with
  `ERROR 1062 (23000): Duplicate entry 'job-7-1' for key 'money_ledger.ledger_ref'`.
- `drifted` is `0`, so every stored balance equals the sum of its ledger rows.
- A credit past the cap changes no row and leaves no ledger row behind.

## Sources (2026)

- https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html
- https://dev.mysql.com/doc/refman/8.4/en/integer-types.html
- https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html
