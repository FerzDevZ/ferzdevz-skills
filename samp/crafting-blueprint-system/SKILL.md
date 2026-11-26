---
name: crafting-blueprint-system
description: Use when crafting needs validated, atomic recipes.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql, gameplay, economy]
    category: samp
---

# Crafting is a database transaction, not a dialog

Ingredients must be removed exactly once and the output granted exactly once. The
first exploit is a replayed craft request still waiting on its ingredient check.

## When to Use

- Players can craft without owning the ingredients, or spend the same stack twice.
- Recipe ids, quantities or craft times arrive from the client.
- A craft interrupted by disconnect or reload duplicates or loses items.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | `OnPlayerDisconnect` fires before the slot is reused |
| Database | MariaDB 11.4 / MySQL 8.4 | transactions, row locks, `CHECK` constraints |
| Timer | `SetTimerEx`, one per player | duration comes from the blueprint row, not the client |
| Tables | InnoDB only | MyISAM ignores transactions, which removes the guarantee |

## Production Implementation

1. Model inputs as rows, not as a fixed column list; the job row is the receipt.

```sql
CREATE TABLE blueprint (
  id INT UNSIGNED PRIMARY KEY, output_item VARCHAR(32) NOT NULL,
  output_amount INT UNSIGNED NOT NULL, station TINYINT UNSIGNED NOT NULL,
  craft_ms INT UNSIGNED NOT NULL) ENGINE=InnoDB;
CREATE TABLE blueprint_input (
  blueprint_id INT UNSIGNED NOT NULL, item_id VARCHAR(32) NOT NULL,
  amount INT UNSIGNED NOT NULL, PRIMARY KEY (blueprint_id, item_id),
  CONSTRAINT blueprint_input_bp_fk FOREIGN KEY (blueprint_id) REFERENCES blueprint (id)
) ENGINE=InnoDB;
CREATE TABLE craft_job (
  player_id INT UNSIGNED PRIMARY KEY, blueprint_id INT UNSIGNED NOT NULL,
  finish_at DATETIME NOT NULL) ENGINE=InnoDB;
```

2. Reserve ingredients in one transaction: `ROW_COUNT()` must equal the input rows.

```sql
CREATE PROCEDURE craft_start(IN p_player INT UNSIGNED, IN p_bp INT UNSIGNED)
BEGIN
  DECLARE v_need INT DEFAULT 0;  DECLARE v_ms INT DEFAULT 0;  DECLARE v_ok INT DEFAULT 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; SELECT 1 AS status, 0 AS craft_ms; END;
  START TRANSACTION;
  SELECT craft_ms INTO v_ms FROM blueprint WHERE id = p_bp FOR UPDATE;
  IF v_ms IS NULL THEN
    ROLLBACK; SELECT 2 AS status, 0 AS craft_ms;            -- unknown blueprint
  ELSE
    SELECT COUNT(*) INTO v_need FROM blueprint_input WHERE blueprint_id = p_bp;
    UPDATE inventory i JOIN blueprint_input bi
        ON bi.item_id = i.item_id AND bi.blueprint_id = p_bp
       SET i.amount = i.amount - bi.amount
     WHERE i.player_id = p_player AND i.amount >= bi.amount;
    SET v_ok = (ROW_COUNT() = v_need);
    IF v_ok = 0 THEN
      ROLLBACK; SELECT 3 AS status, 0 AS craft_ms;          -- missing ingredients
    ELSE
      INSERT INTO craft_job (player_id, blueprint_id, finish_at)
        VALUES (p_player, p_bp, NOW() + INTERVAL v_ms / 1000 SECOND);
      COMMIT; SELECT 0 AS status, v_ms AS craft_ms;
    END IF;
  END IF;
END
```

3. Grant in a second transaction that only accepts a job past `finish_at`.

```sql
CREATE PROCEDURE craft_finish(IN p_player INT UNSIGNED)
BEGIN
  DECLARE v_bp INT DEFAULT NULL;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; SELECT 1 AS status; END;
  START TRANSACTION;
  SELECT blueprint_id INTO v_bp FROM craft_job
   WHERE player_id = p_player AND finish_at <= NOW() FOR UPDATE;
  IF v_bp IS NULL THEN
    ROLLBACK; SELECT 4 AS status;                          -- nothing ready
  ELSE
    INSERT INTO inventory (player_id, item_id, amount)
      SELECT p_player, b.output_item, b.output_amount FROM blueprint b WHERE b.id = v_bp
      ON DUPLICATE KEY UPDATE amount = inventory.amount + VALUES(amount);
    DELETE FROM craft_job WHERE player_id = p_player;
    COMMIT; SELECT 0 AS status;
  END IF;
END
```

4. Validate in Pawn first: connected, spawned, on foot, one craft, id in range.

```pawn
forward PlayerRow(playerid);            // project helper: playerid -> players.id (0 when absent)

stock bool:CraftStart(playerid, blueprintid)
{
    if (!IsPlayerConnected(playerid) || !IsPlayerSpawned(playerid)) return false;
    if (IsPlayerInAnyVehicle(playerid) || g_Crafting[playerid]) return false;
    if (blueprintid < 1 || blueprintid > 64) return false;

    new query[96];
    mysql_format(g_DB, query, sizeof query, "CALL craft_start(%d, %d)", PlayerRow(playerid), blueprintid);
    mysql_tquery(g_DB, query, "OnCraftStart", "dd", playerid, blueprintid);
    return true;
}
```

5. The callback starts the timer with the returned duration; `CRAFT_NOT_READY` retries.

```pawn
public OnCraftStart(playerid, blueprintid)
{
    new rows, status = CRAFT_DB_ERROR, ms = 0;
    cache_get_row_count(rows);
    if (rows > 0)
    {
        cache_get_value_name_int(0, "status", status);
        cache_get_value_name_int(0, "craft_ms", ms);
    }
    if (status == CRAFT_OK)
    {
        g_Crafting[playerid] = true;
        g_CraftTimer[playerid] = SetTimerEx("OnCraftFinishTimer", ms, false, "d", playerid);
    }
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Ingredients deducted, no item | crash between the two procedures | `craft_job` is the receipt: rerun `craft_finish` on login |
| Item granted twice | timer fired twice, or two callbacks for one request | delete the job row inside the grant transaction |
| Craft works with one of three ingredients | `ROW_COUNT()` compared against 1, not the input count | compare to `COUNT(*)` from `blueprint_input` |
| Inventory goes negative | `UPDATE` without `AND amount >= bi.amount` | keep the guard in `WHERE` and add `CHECK (amount >= 0)` |

## Verification

```bash
mariadb -uomp -p server < db/002_crafting.sql
mariadb -uomp -p server -e "INSERT INTO inventory VALUES (11,'cloth',3),(11,'herb',1),(11,'bandage',0);
CALL craft_start(11,1); CALL craft_finish(11);
SELECT item_id, amount FROM inventory WHERE player_id=11 ORDER BY item_id;
SELECT COUNT(*) AS negatives FROM inventory WHERE amount < 0;"
pawncc -i$HOME/samp-sdk/omp-stdlib -i$HOME/samp-sdk/plugins/include -d3 '-;+' '-(' \
  crafting.pwn -ocrafting.amx
```

- The `SELECT` returns `bandage 2`, `cloth 0`, `herb 0` (inputs once, output
  once) and `negatives` is `0`.
- `pawncc` prints no `error` or `warning` line; any diagnostic means the callback
  signature or the `cache_get_value_name_int` call is wrong.

## Sources (2026)

- https://mariadb.com/kb/en/start-transaction/
- https://mariadb.com/kb/en/innodb-locking-reads/
- https://github.com/pBlueG/SA-MP-MySQL
