---
name: vehicle-data-persistence
description: Use when vehicles reset or duplicate after restart.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, vehicles, persistence]
    category: samp
---

# Persist vehicles by row id, not by pool id

`vehicleid` is a pool slot handed out in creation order, freed by `DestroyVehicle`, and reused by
whatever is created next. Key on your own `uid`; rebuild the pool id at boot.

## When to Use

- Parked cars return to the map-editor spawn point after a restart.
- A restart doubles the fleet, or two rows appear for one car.
- Colour, plate, health or panel damage is lost while the row itself survives.

## Compatibility & Stack Matrix (2026)

| Behaviour | open.mp 1.6.x | SA-MP 0.3.7-R2 |
| --- | --- | --- |
| Vehicle pool | `MAX_VEHICLES` 2000, ids 1-1999 | same |
| Restore spawn point | `SetVehicleSpawnInfo` (omp 1.1.0.2612+) | `SetVehiclePos` + `SetVehicleZAngle` |
| Read spawn point | `GetVehicleSpawnInfo` (omp 1.1.0.2612+) | none, track it yourself |
| Damage fields | typed `VEHICLE_PANEL_STATUS` etc. | same bits, untyped |
| Pool id stability | slot reused after destroy | same |
| DB access | open.mp MySQL component or BlueG R41-4 | BlueG R41-4 only |

## Production Implementation

1. One table, your key, plus the spawn point and the four damage words:

```sql
CREATE TABLE IF NOT EXISTS vehicles (
    uid     INT PRIMARY KEY,
    model   SMALLINT NOT NULL,
    spawn_x FLOAT NOT NULL, spawn_y FLOAT NOT NULL, spawn_z FLOAT NOT NULL, spawn_a FLOAT NOT NULL,
    colour1 TINYINT NOT NULL DEFAULT 1,  colour2 TINYINT NOT NULL DEFAULT 1,
    health  FLOAT NOT NULL DEFAULT 1000.0,
    panels  INT NOT NULL DEFAULT 0,  doors INT NOT NULL DEFAULT 0,
    lights  INT NOT NULL DEFAULT 0,  tyres INT NOT NULL DEFAULT 0,
    respawn INT NOT NULL DEFAULT 300,
    plate   VARCHAR(16)
);
```

2. Keep both directions in RAM; `0` means unmanaged because the pool starts at 1:

```pawn
new g_VehUid[MAX_VEHICLES + 1];   // pool id -> uid
new g_VehId[MAX_VEHICLES + 1];    // uid -> pool id
new bool:g_VehDirty[MAX_VEHICLES + 1];
new g_VehCount;
```

3. Load once at boot, ordered by `uid`, before any filterscript creates a vehicle: creation
   order defines the pool ids, so a second creator shifts every mapping by one.

```pawn
public OnGameModeInit()
{
    new DBResult:res = mysql_query(gDB, "SELECT uid, model, spawn_x, spawn_y, spawn_z, spawn_a, colour1, colour2, health, panels, doors, lights, tyres, respawn FROM vehicles ORDER BY uid");
    new rows = (res != DBResult:0) ? cache_get_row_count() : 0;
    for (new row = 0; row < rows; row++)
    {
        new uid, model, c1, c2, respawn, panels, doors, lights, tyres, Float:x, Float:y, Float:z, Float:a, Float:hp;
        cache_get_value_index_int(row, 0, uid);     cache_get_value_index_int(row, 1, model);
        cache_get_value_index_float(row, 2, x);     cache_get_value_index_float(row, 3, y);
        cache_get_value_index_float(row, 4, z);     cache_get_value_index_float(row, 5, a);
        cache_get_value_index_int(row, 6, c1);      cache_get_value_index_int(row, 7, c2);
        cache_get_value_index_float(row, 8, hp);    cache_get_value_index_int(row, 9, panels);
        cache_get_value_index_int(row, 10, doors);
        cache_get_value_index_int(row, 11, lights); cache_get_value_index_int(row, 12, tyres);
        cache_get_value_index_int(row, 13, respawn);

        new vehid = CreateVehicle(model, x, y, z, a, c1, c2, respawn);
        if (vehid == INVALID_VEHICLE_ID) continue;
        g_VehUid[vehid] = uid;   g_VehId[uid] = vehid;   g_VehCount++;
        Vehicle_Restore(vehid, model, x, y, z, a, c1, c2, respawn, hp, panels, doors, lights, tyres);
    }
    printf("VEH boot rows=%d created=%d", rows, g_VehCount);
    SetTimer("Vehicle_Flush", 30000, true);
    return 1;
}
```

4. Restore spawn info, not just position: `SetVehicleSpawnInfo` is what sends
   `OnVehicleDeath` and `SetVehicleToRespawn` back to the stored point.

```pawn
stock Vehicle_Restore(vehid, model, Float:x, Float:y, Float:z, Float:a, c1, c2, respawn, Float:hp, panels, doors, lights, tyres)
{
    SetVehicleSpawnInfo(vehid, model, x, y, z, a, c1, c2, respawn);
    SetVehicleHealth(vehid, hp);
    UpdateVehicleDamageStatus(vehid, VEHICLE_PANEL_STATUS:panels, VEHICLE_DOOR_STATUS:doors, VEHICLE_LIGHT_STATUS:lights, VEHICLE_TYRE_STATUS:tyres);
}
```

5. Mark dirty on durable changes only (damage, death, colour, plate, driver exit). Never save
   inside `OnVehicleDamageStatusUpdate`; it fires per panel per hit.

6. Flush on a timer and on exit. One `UPDATE ... WHERE uid=?` per dirty row is idempotent: a
   crash between flushes costs seconds of state, never a row.

```pawn
forward Vehicle_Flush();
public Vehicle_Flush()
{
    for (new uid = 1; uid <= g_VehCount; uid++)
    {
        new vehid = g_VehId[uid];
        if (vehid == 0 || !g_VehDirty[vehid]) continue;
        Vehicle_Save(uid, vehid);   g_VehDirty[vehid] = false;
    }
    return 1;
}

stock Vehicle_Save(uid, vehid)
{
    new Float:x, Float:y, Float:z, Float:a, Float:hp, panels, doors, lights, tyres;
    GetVehiclePos(vehid, x, y, z);   GetVehicleZAngle(vehid, a);
    GetVehicleHealth(vehid, hp);     GetVehicleDamageStatus(vehid, panels, doors, lights, tyres);

    static q[256];
    format(q, sizeof q, "UPDATE vehicles SET health=%f, panels=%d, doors=%d, lights=%d, tyres=%d WHERE uid=%d", hp, panels, doors, lights, tyres, uid);
    mysql_tquery(gDB, q);
}
```

7. Write `spawn_*` from the empty-car path (`OnPlayerExitVehicle`), never in the batch, or a
   checkpoint-saved race position becomes a permanent spawn point. Reconcile after the load: if
   `created != rows`, refuse to flush, or it writes defaults over the rows it never read.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Fleet doubles on the second restart | rows keyed on `vehicleid`, re-inserted each boot | `uid` primary key, seed once with `INSERT IGNORE` |
| Right count, wrong cars | mapping assumed pool ids are stable | rebuild `uid -> vehicleid` during load |
| Cars snap back to the editor spawn | live position saved, no spawn info | `SetVehicleSpawnInfo` after `CreateVehicle` |
| Health resets to 1000 after a crash | flush rewrote rows it had not loaded | abort flush when `created != rows` |
| Cars pile on one coordinate | one global spawn reused for every row | store `spawn_x/y/z/a` per row |
| Server hitches on every bullet hit | synchronous save in `OnVehicleDamageStatusUpdate` | dirty flag plus 30 s batch |

## Verification

```bash
mysql -N -e "SELECT COUNT(*), COUNT(DISTINCT uid) FROM vehicles" omp
grep 'VEH boot' log.txt | tail -2
```

```text
240	240
VEH boot rows=240 created=240
VEH boot rows=240 created=240
```

`rows == created` on both boots proves nothing was skipped; a mismatch means a duplicate `uid`
or a failed `CreateVehicle`.

## Sources (2026)

- https://open.mp/docs/scripting/resources/limits
- https://open.mp/docs/scripting/functions/SetVehicleSpawnInfo
- https://open.mp/docs/scripting/functions/GetVehicleSpawnInfo
