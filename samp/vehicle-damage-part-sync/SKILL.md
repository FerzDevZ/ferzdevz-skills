---
name: vehicle-damage-part-sync
description: Use when panel, door or tyre damage is lost on respawn.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, vehicles, damage]
    category: samp
---

# Persist panel, door, light and tyre damage as four words

Health and damage are separate state. `SetVehicleHealth` gives you a burning engine and a
pristine body; `UpdateVehicleDamageStatus` gives you missing doors and popped tyres with full
health. Persist the four words, never the decoded parts.

## When to Use

- Panels, doors, lights or tyres reset on respawn or after a restart.
- A repaired car still shows a hanging door, or a damaged car looks new.
- Two players see different damage on the same vehicle.
- Health is stored but the body always looks undamaged after a restore.

## Compatibility & Stack Matrix (2026)

| Item | open.mp 1.6.x | SA-MP 0.3.7-R2 |
| --- | --- | --- |
| Params | `VEHICLE_PANEL_STATUS:` / `_DOOR_` / `_LIGHT_` / `_TYRE_STATUS:` | plain `int` |
| Read | `GetVehicleDamageStatus(vehid, panels, doors, lights, tyres)` | same order |
| Write | `UpdateVehicleDamageStatus`, returns nothing | same |
| Callback | `OnVehicleDamageStatusUpdate(vehicleid, playerid)` | same |
| Health changes | do not fire the callback | same |
| Windshield nibble | readable, write has no visual effect | same |

`OnVehicleDamageStatusUpdate` reports the change only; it never tells you which panel.
Read the four words inside it and diff against your stored copy.

## Production Implementation

1. Declare typed variables, because open.mp tags the parameters and an untyped `new panels`
   produces tag-mismatch warnings at `-d3`.

```pawn
new VEHICLE_PANEL_STATUS:panels;
new VEHICLE_DOOR_STATUS:doors;
new VEHICLE_LIGHT_STATUS:lights;
new VEHICLE_TYRE_STATUS:tyres;
GetVehicleDamageStatus(vehid, panels, doors, lights, tyres);
```

2. Know the layout before writing a single mask. Bits count from the right, low bit first:

| Word | Field | Bits | Values |
| --- | --- | --- | --- |
| panels | front-left, front-right, rear-left, rear-right | 0, 4, 8, 12 | 0-3 each |
| panels | windshield, front bumper, rear bumper | 16, 20, 24 | 0-3 each |
| doors | bonnet, boot, driver, passenger | 0-2, 8-10, 16-18, 24-26 | 0-7 each |
| lights | front-left, front-right, back | 0, 2, 6 | 0-1 each |
| tyres | rear-right, front-right, rear-left, front-left | 0, 1, 2, 3 | 0-1 each |

3. Pack panels with nibble shifts; the documented reference value for two removed bumpers is
   `53477376`, which is a cheap unit test for your encoder.

```pawn
stock PackPanels(fl, fr, rl, rr, wind, fb, rb) { return (fl&3)|((fr&3)<<4)|((rl&3)<<8)|((rr&3)<<12)|((wind&3)<<16)|((fb&3)<<20)|((rb&3)<<24); }
stock PackTyres(rr, fr, rl, fl) { return (rr&1)|((fr&1)<<1)|((rl&1)<<2)|((fl&1)<<3); }
```

4. Apply, then read back and keep what the server accepted. Bikes expose two tyre bits and
   some models ignore panels, so the server value is the only truth worth persisting.

```pawn
stock Vehicle_ApplyDamage(vehid, &panels, &doors, &lights, &tyres)
{
    UpdateVehicleDamageStatus(vehid, VEHICLE_PANEL_STATUS:panels, VEHICLE_DOOR_STATUS:doors, VEHICLE_LIGHT_STATUS:lights, VEHICLE_TYRE_STATUS:tyres);
    new VEHICLE_PANEL_STATUS:p, VEHICLE_DOOR_STATUS:d, VEHICLE_LIGHT_STATUS:l, VEHICLE_TYRE_STATUS:t;
    GetVehicleDamageStatus(vehid, p, d, l, t);
    panels = _:p;   doors = _:d;   lights = _:l;   tyres = _:t;
}
```

5. Repair explicitly clears the words. `RepairVehicle` restores health and the visual model,
   but the four bitfields are separate state and can survive it:

```pawn
stock Vehicle_FullRepair(vehid)
{
    RepairVehicle(vehid);
    UpdateVehicleDamageStatus(vehid, VEHICLE_PANEL_STATUS:0, VEHICLE_DOOR_STATUS:0, VEHICLE_LIGHT_STATUS:0, VEHICLE_TYRE_STATUS:0);
}
```

6. Force a panel restream when the state must be exact. Going 0 -> 1 -> 2 leaves a panel
   crushed *and* hanging; clear the nibble to 0 first, then write the target state.

```pawn
stock Vehicle_SetPanel(vehid, nibble, state)
{
    new VEHICLE_PANEL_STATUS:p, VEHICLE_DOOR_STATUS:d, VEHICLE_LIGHT_STATUS:l, VEHICLE_TYRE_STATUS:t;
    GetVehicleDamageStatus(vehid, p, d, l, t);
    new v = _:p, shift = nibble * 4;
    v = (v & ~(3 << shift)) | ((state & 3) << shift);
    UpdateVehicleDamageStatus(vehid, VEHICLE_PANEL_STATUS:v, d, l, t);
}
```

7. Persist the four words next to health in the vehicle row and restore them after
   `CreateVehicle`. Do the restore before the vehicle is streamed to anyone, so nobody sees
   the undamaged model first.

8. Store only on change: diff inside `OnVehicleDamageStatusUpdate`, set a dirty flag, flush in
   the same 30 s batch as the rest of the vehicle row.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Damage gone after restart | only health persisted | store panels, doors, lights, tyres |
| Panel crushed and hanging at once | 0 -> 1 -> 2 transition on one nibble | clear the nibble to 0, then set 2 |
| Broken door after `/repair` | `RepairVehicle` does not clear the words | explicit all-zero `UpdateVehicleDamageStatus` |
| Wrong tyre pops on a bike | 4-bit tyre mask written to a 2-bit bike | persist the value read back from the server |
| Damage reappears a second later | restore applied, then respawn reset the vehicle | apply after respawn, not before |
| Database grows per impact | one row write per callback | dirty flag plus batch flush |
| Windshield damage never shows | nibble is read-only for visuals | do not build gameplay on it |

## Verification

Encoder check against the documented example (two bumpers removed):

```bash
python3 -c "p=lambda v: v[0]|v[1]<<4|v[2]<<8|v[3]<<12|v[4]<<16|v[5]<<20|v[6]<<24; print(p([0,0,0,0,0,3,3]))"
```

```text
53477376
```

Round trip in the game, after a repair and a restart:

```pawn
printf("DMG veh=%d p=%d d=%d l=%d t=%d", vehid, _:panels, _:doors, _:lights, _:tyres);
```

```text
DMG veh=41 p=0 d=196608 l=1 t=0
```

The same four numbers before the restart and after the respawn are the proof; a changed word
means the restore ran before the vehicle was respawned and was overwritten.

## Sources (2026)

- https://open.mp/docs/scripting/resources/damagestatus
- https://open.mp/docs/scripting/functions/UpdateVehicleDamageStatus
- https://open.mp/docs/scripting/callbacks/OnVehicleDamageStatusUpdate
