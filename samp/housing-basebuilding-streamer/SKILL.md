---
name: housing-basebuilding-streamer
description: Use when house furniture vanishes after a restart.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql, streamer, housing, persistence]
    category: samp
---

# Furniture lives in a table; the object is only a view of that row

Base building loses data for one reason: the object is treated as the source of
truth. A moved sofa exists only in RAM until someone writes its transform. Persist
every placement as a row, load rows only for the house the player is inside, and
take the editing lock in SQL where two clients cannot both win.

## When to Use

- Furniture placed yesterday is gone after a restart or a `gmx`.
- Two admins drag the same sofa and one placement overwrites the other.
- Object count grows all day and the streamer starts dropping furniture.
- Not for the object budget itself — that is `incognito-streamer-tuning`.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.6.x | callbacks plus `GetPlayerVirtualWorld` |
| Streamer | 2.9.6 | `CreateDynamicObject`, `MoveDynamicObject`, `DestroyDynamicObject` |
| Streamer callback | `OnDynamicObjectMoved` | fires when a `MoveDynamicObject` finishes |
| MySQL plugin | BlueG R41-4 | `mysql_tquery`, `cache_affected_rows` |
| Database | MySQL 8.4 / MariaDB 10.11 | InnoDB, FK with `ON DELETE CASCADE` |
| World model | one virtual world per house | `1000 + houseid`, interior from the house row |

## Production Implementation

1. Model the rows first. The transform belongs to the furniture row; the world and
   interior belong to the house, so a house can be relocated without touching every
   object.

```sql
CREATE TABLE houses (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT, owner INT UNSIGNED NULL,
  world SMALLINT UNSIGNED NOT NULL, interior TINYINT UNSIGNED NOT NULL DEFAULT 0,
  price INT UNSIGNED NOT NULL DEFAULT 0, editor INT UNSIGNED NULL,
  editor_since TIMESTAMP NULL,
  PRIMARY KEY (id), KEY h_owner (owner)
) ENGINE=InnoDB;

CREATE TABLE furniture (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT, house_id INT UNSIGNED NOT NULL,
  model SMALLINT UNSIGNED NOT NULL,
  x FLOAT NOT NULL, y FLOAT NOT NULL, z FLOAT NOT NULL,
  rx FLOAT NOT NULL DEFAULT 0, ry FLOAT NOT NULL DEFAULT 0, rz FLOAT NOT NULL DEFAULT 0,
  PRIMARY KEY (id), KEY f_house (house_id),
  CONSTRAINT fk_furn_house FOREIGN KEY (house_id) REFERENCES houses(id) ON DELETE CASCADE
) ENGINE=InnoDB;
```

2. Load on entry, not at boot: creating objects for 400 houses at startup wastes the
   streamer budget, and the player only ever sees one house. Guard against a second
   load, then query the house rows and pass the id to the callback:
   `mysql_tquery(g_DB, q, "OnFurnitureLoaded", "d", houseid);`

3. Create each object in the house world with the house interior, and keep the
   handle so a later move or delete does not need a lookup.

```pawn
forward OnFurnitureLoaded(houseid);
public OnFurnitureLoaded(houseid)
{
    new rows = cache_num_rows(), world = 1000 + houseid, model;
    new Float:x, Float:y, Float:z, Float:rx, Float:ry, Float:rz;
    for (new i = 0; i < rows && i < MAX_FURN; i++)
    {
        cache_get_value_name_int(i, "model", model);
        cache_get_value_name_float(i, "x", x);
        cache_get_value_name_float(i, "y", y);
        cache_get_value_name_float(i, "z", z);
        cache_get_value_name_float(i, "rx", rx);
        cache_get_value_name_float(i, "ry", ry);
        cache_get_value_name_float(i, "rz", rz);
        g_HouseObj[houseid][g_HouseFurnCount[houseid]++] = CreateDynamicObject(model,
            x, y, z, rx, ry, rz, world, g_HouseInterior[houseid], -1, 200.0, 200.0);
    }
    return 1;
}
```

4. Take the edit lock in SQL, not in a Pawn boolean. `cache_affected_rows` is the
   only answer that is true across two server processes and a reconnect.

```pawn
stock TryLockHouse(playerid, houseid)
{
    new q[256];
    format(q, sizeof q, "UPDATE houses SET editor = %d, editor_since = NOW() \
        WHERE id = %d AND (editor IS NULL OR editor = %d \
        OR editor_since < NOW() - INTERVAL 10 MINUTE)", g_Account[playerid], houseid, g_Account[playerid]);
    mysql_tquery(g_DB, q, "OnHouseLocked", "dd", playerid, houseid);
    return 1;
}
```

5. Persist on the event that ends a move, not a timer: `OnDynamicObjectMoved` means
   the transform is final, so no halfway position is written. Enforce the per-house
   cap server-side before an insert; a client-side count is a suggestion.

```pawn
public OnDynamicObjectMoved(STREAMER_TAG_OBJECT:objectid)
{
    if (g_MovingPlayer[objectid] == INVALID_PLAYER_ID) return 1;
    new Float:x, Float:y, Float:z, Float:rx, Float:ry, Float:rz, q[256];
    GetDynamicObjectPos(objectid, x, y, z);
    GetDynamicObjectRot(objectid, rx, ry, rz);
    format(q, sizeof q, "UPDATE furniture SET x=%.3f, y=%.3f, z=%.3f, rx=%.1f, ry=%.1f, rz=%.1f WHERE id=%d",
        x, y, z, rx, ry, rz, g_MovingRow[objectid]);
    mysql_tquery(g_DB, q);
    return 1;
}
```

6. Destroy on exit **and** on disconnect. A player who crashes inside a house leaves
   the objects behind if the unload only runs from an exit command.

```pawn
stock UnloadFurniture(houseid)
{
    for (new i = 0; i < g_HouseFurnCount[houseid]; i++)
        if (IsValidDynamicObject(g_HouseObj[houseid][i])) DestroyDynamicObject(g_HouseObj[houseid][i]);
    g_HouseFurnCount[houseid] = 0;
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Everything is gone after restart | objects created, transform never written | write the row in `OnDynamicObjectMoved` |
| Two admins fight over one sofa | Pawn boolean lock, per-process | SQL `UPDATE ... WHERE editor IS NULL` plus `cache_affected_rows` |
| Furniture visible from the street | house world left at `-1` or 0 | world `1000 + houseid` on every object |
| Object count climbs all session | unloading only on a command | unload on exit and on disconnect |
| Furniture missing for one player only | objects created in the `playerid` slot | pass `-1` as the player argument, use world and interior |
| Edit lock sticks after a crash | `editor` set, never cleared | the `editor_since` timeout clause |

## Verification

```bash
mysql -N -B -e "SELECT house_id, COUNT(*) FROM samp.furniture GROUP BY house_id ORDER BY house_id LIMIT 3;"
```

```text
1	12
2	7
```

- Restart, walk into house 1, run `/furncount`: `house=1 objects=12 db=12` means the
  load reads the same rows the editor wrote.
- `Streamer_CountItems(STREAMER_TYPE_OBJECT)` returns to its pre-entry value after exit.
- With two clients on `/house edit 1` the second is refused; `SELECT editor FROM
  houses WHERE id=1` names only the first.

## Sources (2026)

- https://raw.githubusercontent.com/samp-incognito/samp-streamer-plugin/master/streamer.inc
- https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html
- https://raw.githubusercontent.com/pBlueG/SA-MP-MySQL/master/a_mysql.inc.in
