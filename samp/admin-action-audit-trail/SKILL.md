---
name: admin-action-audit-trail
description: Use when admin actions need a provable audit trail.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql, security, audit]
    category: samp
---

# One row per admin action, written inside the same transaction

A ban, a balance edit or a score reset is a state change plus an explanation.
If the explanation lives in chat or in a log file, the first restart or `/gmx`
erases it and nobody can answer "who unbanned him and why". Keep the actor, the
before/after snapshot and the reason in one table, written by one stored
procedure that also performs the change, so a crash cannot leave a change
without its row or a row without its change.

## When to Use

- Staff commands change money, level, ban state or inventory and nobody can explain a result.
- Two admins touch the same account and you need to know which one won.
- An appeal arrives weeks later and the reason string is gone from the console buffer.
- You need per-admin counts ("who banned 40 people this week") without parsing logs.
- A destructive command must be refused when the operator gives no reason.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | `BanEx`, `GetPlayerIp`, `GetPlayerName` are real natives |
| DB driver | BlueG MySQL R41-4 | `mysql_format` with `%e` escapes the string |
| Database | MySQL 8.4 / MariaDB 10.11 | `START TRANSACTION`, `SELECT ... FOR UPDATE`, `JSON_OBJECT` |
| Storage engine | InnoDB | only InnoDB gives row locks and rollback |
| Actor identity | `accounts.id`, not nickname | nicknames change, ids do not |
| Panel access | read-only user | `SELECT` grant only, never `UPDATE` |

## Production Implementation

1. Create the table before the first command ships. Snapshots are JSON so a new
   audited field does not need a migration.

```sql
CREATE TABLE admin_actions (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  actor_id    INT UNSIGNED    NOT NULL,
  actor_name  VARCHAR(24)     NOT NULL,
  actor_ip    VARCHAR(45)     NOT NULL,
  target_id   INT UNSIGNED    NOT NULL,
  target_name VARCHAR(24)     NOT NULL,
  action      VARCHAR(32)     NOT NULL,
  before_json JSON            NULL,
  after_json  JSON            NULL,
  reason      VARCHAR(190)    NOT NULL,
  created_at  TIMESTAMP(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  KEY actor_time (actor_id, created_at),
  KEY target_time (target_id, created_at)
) ENGINE=InnoDB;
```

2. Perform the change and the audit insert in one procedure. `FOR UPDATE` locks
   the target row so two admins cannot interleave a read-modify-write.

```sql
DELIMITER $$
CREATE PROCEDURE admin_set_score(
  IN p_actor INT, IN p_actor_name VARCHAR(24), IN p_actor_ip VARCHAR(45),
  IN p_target INT, IN p_reason VARCHAR(190), IN p_score INT)
BEGIN
  DECLARE v_old INT DEFAULT 0;
  IF p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason)) < 4 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'reason required';
  END IF;
  START TRANSACTION;
  SELECT score INTO v_old FROM accounts WHERE id = p_target FOR UPDATE;
  UPDATE accounts SET score = p_score WHERE id = p_target;
  INSERT INTO admin_actions
    (actor_id, actor_name, actor_ip, target_id, target_name, action,
     before_json, after_json, reason)
  SELECT p_actor, p_actor_name, p_actor_ip, p_target, name, 'set_score',
         JSON_OBJECT('score', v_old), JSON_OBJECT('score', p_score), p_reason
    FROM accounts WHERE id = p_target;
  COMMIT;
END$$
DELIMITER ;
```

3. Call the procedure from Pawn with escaping done by the driver. `%e` quotes
   and escapes the string; never build the query with `format` alone.

```pawn
stock AdminSetScore(adminid, targetid, score, const reason[])
{
    new q[512], actor[24], ip[46];
    GetPlayerName(adminid, actor, sizeof actor);
    GetPlayerIp(adminid, ip, sizeof ip);
    mysql_format(g_DB, q, sizeof q,
        "CALL admin_set_score(%d, '%e', '%e', %d, '%e', %d)",
        g_AccountID[adminid], actor, ip, g_AccountID[targetid], reason, score);
    mysql_tquery(g_DB, q, "OnAdminActionLogged", "dd", adminid, targetid);
    return 1;
}

forward OnAdminActionLogged(adminid, targetid);
public OnAdminActionLogged(adminid, targetid)
{
    if (mysql_errno(g_DB) != 0)
        SendClientMessage(adminid, 0xFF4444FF, "Action failed and was rolled back.");
}
```

4. Take the reason from a dialog, not from the command string. `/setscore 12
   5000` opens `DIALOG_STYLE_INPUT` and passes its text to the stock above; an
   empty answer cancels instead of writing a blank reason.

5. Never write the audit row from a second query after the change already
   happened. Two `mysql_tquery` calls on a pooled connection are two
   transactions, and the pool may hand them to different sessions.

6. Give the panel a read-only account and a fixed view. Staff see the last 50
   global rows; nobody reads the raw table.

```sql
CREATE VIEW admin_actions_recent AS
  SELECT id, actor_name, target_name, action, before_json, after_json, reason, created_at
    FROM admin_actions ORDER BY id DESC LIMIT 500;
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Change applied, no audit row | two separate queries, the second failed | both statements inside the procedure; check `mysql_errno` in the callback |
| `reason` is empty | command syntax allowed skipping it | require a dialog and reject `CHAR_LENGTH(TRIM(reason)) < 4` |
| Audit row exists, change missing | insert outside the transaction | insert after `UPDATE`, before `COMMIT`, same procedure |
| Wrong admin blamed | actor taken from a global "last admin" variable | pass actor id, name and ip as procedure parameters |
| Duplicate rows per action | callback re-ran the procedure on retry | dedupe on `(actor_id, target_id, created_at)` or make the action idempotent |
| `Lock wait timeout exceeded` | long transaction holding `FOR UPDATE` | lock, update, insert, commit - no network calls inside |

## Verification

```bash
mysql samp -e "CALL admin_set_score(1,'TestAdmin','127.0.0.1',42,'verify trail',5000);"
mysql samp -e "SELECT actor_name,target_name,before_json,after_json,reason \
               FROM admin_actions ORDER BY id DESC LIMIT 1;"
mysql samp -e "CALL admin_set_score(1,'TestAdmin','127.0.0.1',42,'',1);" \
  || echo "refused as expected"
```

- The `SELECT` returns one row with `before_json {"score": <old>}` and
  `after_json {"score": 5000}`: the snapshot came from the same transaction.
- The second `CALL` fails with `reason required` (SQLSTATE 45000) and adds no row.
- In game, `/setscore` on a test account writes one row and the panel lists it
  under the acting admin within the same second.

## Sources (2026)

- https://open.mp/docs/scripting/functions/BanEx
- https://mariadb.com/kb/en/start-transaction/
- https://github.com/pBlueG/SA-MP-MySQL
