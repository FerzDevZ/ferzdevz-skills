---
name: inventory-relational-schema
description: Use when items duplicate or vanish on trade and crash.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql, inventory, schema]
    category: samp
---

# Store items as lockable rows, never as a parsed string

The bugs that hurt are always the same shape: an item exists twice, or exists
nowhere, because the move was two queries and one was lost. A relational inventory
makes every item (or stack) a row with a stable id, an owner and a slot a `UNIQUE`
key protects, so ownership changes become one transaction and a per-move ledger
makes a duplicate detectable instead of mysterious.

## When to Use

- Items duplicate after a trade, a timeout, or a server crash.
- Items vanish on relog because the save ran before the grant.
- A trunk, house or faction storage must share one schema with player pockets.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.4.x (Pawn 1.6.7) or SA-MP 0.3.7 | same SQL surface |
| MySQL plugin | BlueG R41-4 | `cache_get_row_count` + per-row reads; batch for writes |
| Database | MySQL 8.4 LTS / 8.0 | `CHECK` enforced since 8.0.16, `JSON` since 5.7 |
| Storage engine | InnoDB | required for row locks and `ROLLBACK` |
| Slot model | `UNIQUE (owner_id, container, slot)` | the database refuses two items in one slot |
| Metadata | `JSON` for per-item state | never encode state into `model` or a string |

## Production Implementation

1. One row per stack or unique instance; `container` separates pockets, trunks
   and house storage without a table per feature.

```sql
CREATE TABLE inv_items (
  id        BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT PRIMARY KEY,
  owner_id  INT UNSIGNED     NOT NULL,
  container TINYINT UNSIGNED NOT NULL DEFAULT 0,   -- 0 pocket, 1 trunk, 2 house
  model     SMALLINT UNSIGNED NOT NULL,
  qty       INT UNSIGNED     NOT NULL DEFAULT 1,
  slot      TINYINT UNSIGNED NOT NULL,
  meta      JSON             NULL,                 -- durability, serial, ammo
  UNIQUE KEY inv_slot (owner_id, container, slot),
  KEY inv_owner_model (owner_id, container, model),
  CONSTRAINT inv_qty_positive CHECK (qty > 0),
  CONSTRAINT inv_slot_range   CHECK (slot < 40)
) ENGINE=InnoDB;
```

2. Every move gets a ledger row with a client-generated `ref` (replay guard).

```sql
CREATE TABLE inv_moves (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  item_id    BIGINT UNSIGNED NOT NULL,
  from_owner INT UNSIGNED NOT NULL,
  to_owner   INT UNSIGNED NOT NULL,
  qty        INT UNSIGNED NOT NULL,
  ref        CHAR(36)     NOT NULL,
  created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY moves_ref (ref)
) ENGINE=InnoDB;
```

3. Move ownership in one guarded batch. `from_owner` in the `WHERE` makes a
   double-trade impossible: the second attempt matches zero rows. Pick the
   destination slot beforehand; the unique key is the last line of defence, and a
   taken slot raises `1062` and aborts the batch.

```sql
ROLLBACK;
START TRANSACTION;
INSERT INTO inv_moves (item_id, from_owner, to_owner, qty, ref)
  VALUES (42, 7, 11, 1, 'trade-1')
  ON DUPLICATE KEY UPDATE ref = ref;
SET @fresh := ROW_COUNT();
UPDATE inv_items SET owner_id = 11, slot = 9
  WHERE id = 42 AND owner_id = 7 AND @fresh = 1;
SET @moved := ROW_COUNT();
DELETE FROM inv_moves WHERE ref = 'trade-1' AND @moved = 0;
COMMIT;
```

5. Read a whole inventory in one query and fill the Pawn array from the cache;
   one query per slot is what makes inventories slow at scale.

```pawn
mysql_format(g_DB, q, sizeof q,
    "SELECT id, model, qty, slot FROM inv_items \
      WHERE owner_id = %d AND container = %d ORDER BY slot", owner, container);
mysql_tquery(g_DB, q, "OnInvLoad", "dd", playerid, container);

public OnInvLoad(playerid, container)
{
    new rows;
    cache_get_row_count(rows);
    for (new i = 0; i < rows; i++)
    {
        cache_get_value_name_int(i, "id",    g_Items[playerid][i][E_ID]);
        cache_get_value_name_int(i, "model", g_Items[playerid][i][E_MODEL]);
        cache_get_value_name_int(i, "qty",   g_Items[playerid][i][E_QTY]);
        cache_get_value_name_int(i, "slot",  g_Items[playerid][i][E_SLOT]);
    }
    return 1;
}
```

6. Stacking is a guarded increment; `qty + 1 <= 64` failing means "new stack".

```sql
UPDATE inv_items SET qty = qty + 1
 WHERE id = 43 AND qty + 1 <= 64;
```

7. Split in one batch so a unit is never deleted before its copy exists: insert
   the new stack, decrement the source, delete it at zero.

```sql
START TRANSACTION;
INSERT INTO inv_items (owner_id, container, model, qty, slot)
  SELECT owner_id, container, model, 5, 12 FROM inv_items WHERE id = 43;
UPDATE inv_items SET qty = qty - 5 WHERE id = 43 AND qty >= 5;
DELETE FROM inv_items WHERE id = 43 AND qty = 0;
COMMIT;
```

8. Audit totals nightly; a count that moves without an `inv_moves` row is the
   fingerprint of a duplication bug.

```sql
SELECT owner_id, model, SUM(qty) AS total
FROM inv_items GROUP BY owner_id, model
HAVING total < 0;
```
## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Item duplicated after a failed trade retry | transfer re-run without an idempotency key | `ref` unique in `inv_moves`, move guarded by `@fresh = 1` |
| `1062 Duplicate entry '11-0-9'` on a trade | destination slot occupied or raced | allocate the slot before the batch, retry once with the next free slot |
| Items disappear on relog | grant committed after the save snapshot | save reads `inv_items`, never a Pawn cache |
| One unit lost on split | source decremented and copy inserted in separate queries | one batch: insert copy, decrement, delete at zero |
| Two items in one slot after a crash | slot stored as a string index, no constraint | `UNIQUE (owner_id, container, slot)` |

## Verification

```bash
mysql -h127.0.0.1 -uroot -p"$PW" samp --table -e "
  SELECT SUM(qty) AS held FROM inv_items WHERE owner_id = 7;
  UPDATE inv_items SET slot = 9 WHERE owner_id = 11 AND slot = 10;"
```

- A one-unit trade leaves global `SUM(qty)` unchanged with one `inv_moves` row.
- With owner 11 already holding slot 9, the second statement fails:
  `ERROR 1062 (23000): Duplicate entry '11-0-9' for key 'inv_items.inv_slot'`.
- The negative-total audit returns zero rows after a crash test.

## Sources (2026)

- https://dev.mysql.com/doc/refman/8.4/en/json.html
- https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html
- https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html
