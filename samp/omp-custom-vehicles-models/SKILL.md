---
name: omp-custom-vehicles-models
description: Use when a guide says AddVehicleModel or custom car models.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, models, vehicles]
    category: samp
---

# Custom vehicle appearance without a vehicle-model native

There is no `AddVehicleModel`, in open.mp 1.6 or in 0.3.DL. The artwork system covers character
models and simple objects only. A "custom car" is colours, paintjobs, components, plus objects
you attach to the body; players who want a new chassis need a client-side mod.

## When to Use

- A tutorial, snippet or assistant answer tells you to call `AddVehicleModel`.
- You need per-vehicle liveries or decals with no client download.
- `AddVehicleComponent` returns 0 and the car stays stock.
- A livery object stays in the world after the car is destroyed.

## Compatibility & Stack Matrix (2026)

| Capability | open.mp 1.6.x | SA-MP 0.3.DL R1 |
| --- | --- | --- |
| `AddVehicleModel` | not in the docs, no native | not in the docs |
| Custom skins (`AddCharModel`) | yes | yes |
| Custom simple objects (`AddSimpleModel`) | yes | yes |
| Colours | `ChangeVehicleColor` | same |
| Paintjobs | `ChangeVehiclePaintjob`, 0-3, 3 removes | same |
| Components | `AddVehicleComponent` | same |
| Server-pushed vehicle model | no | no |

The custom-model docs list exactly seven entries: `AddSimpleModel`, `AddSimpleModelTimed`,
`FindModelFileNameFromCRC`, `FindTextureFileNameFromCRC`, `GetCustomModelPath`,
`IsValidCustomModel`, `RedirectDownload`. No vehicle entry exists.

## Production Implementation

1. Prove the native is absent before designing around it. An invented call fails at compile
   time with `error 017: undefined symbol`, not at runtime:

```bash
grep -rn 'AddVehicleModel' qawno/include/ gamemodes/ | wc -l
```

2. Use colour and paintjob first; they are free and need no download. `ChangeVehiclePaintjob`
   returns true even for a missing vehicle, so validate the id yourself.

```pawn
if (!IsValidVehicle(vehid)) return 0;
ChangeVehicleColor(vehid, 3, 1);
ChangeVehiclePaintjob(vehid, 3);   // 3 removes the paintjob, 0-2 apply one
```

3. Add components by checking the slot afterwards. A component the model does not accept
   returns 0 and leaves nothing behind, so test the slot instead of trusting the return:

```pawn
stock bool:Vehicle_AddPart(vehid, componentid)
{
    if (!AddVehicleComponent(vehid, componentid)) return false;
    return GetVehicleComponentInSlot(vehid, GetVehicleComponentType(componentid)) == componentid;
}
```

4. Reapply appearance from your own row after every spawn. Components and paintjobs are not
   part of the vehicle's saved damage state, so a respawn is a fresh model:

```pawn
public OnVehicleSpawn(vehid)
{
    Vehicle_ApplySavedLook(vehid);   // colour, paintjob, components, livery object
    return 1;
}
```

5. For a livery, attach a retextured object to the body. Size comes from
   `GetVehicleModelInfo(..., VEHICLE_MODEL_INFO_SIZE, ...)`, so the plane sits on the roof
   instead of inside it, and the offset is in vehicle model space, not world space.

```pawn
new g_LiveryObj[MAX_VEHICLES + 1] = { INVALID_OBJECT_ID, ... };

stock Vehicle_ApplyLivery(vehid, objectmodel, const txdname[], const txdtexture[], Float:lift)
{
    new Float:sx, Float:sy, Float:sz;
    GetVehicleModelInfo(GetVehicleModel(vehid), VEHICLE_MODEL_INFO_SIZE, sx, sy, sz);
    if (g_LiveryObj[vehid] != INVALID_OBJECT_ID) DestroyObject(g_LiveryObj[vehid]);
    g_LiveryObj[vehid] = CreateObject(objectmodel, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 300.0);
    SetObjectMaterial(g_LiveryObj[vehid], 0, 0, txdname, txdtexture, 0xFFFFFFFF);
    AttachObjectToVehicle(g_LiveryObj[vehid], vehid, 0.0, 0.0, sz / 2 + lift, 0.0, 0.0, 0.0);
}
```

6. Destroy the livery on death and respawn. The attached object is not owned by the vehicle:
   the docs state it stays where the car disappeared and reattaches to whatever claims that
   vehicle id next, which is how a livery ends up on an unrelated car.

```pawn
public OnVehicleDeath(vehid, killerid)
{
    if (g_LiveryObj[vehid] != INVALID_OBJECT_ID)
    {
        DestroyObject(g_LiveryObj[vehid]);
        g_LiveryObj[vehid] = INVALID_OBJECT_ID;
    }
    return 1;
}
```

7. If the user truly needs a new chassis, say it is a client mod: build the model as a
   replacement for a stock model id, ship it to players, and accept that anyone without it
   sees the stock car. The server cannot verify or push it.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `error 017: undefined symbol "AddVehicleModel"` | native does not exist | use colours, paintjobs, components, attached objects |
| Skin downloads but car stays stock | artwork covers characters and simple objects only | client-side mod, or a livery object |
| `AddVehicleComponent` returns 0 | component not valid for that model | test the slot, skip the part, log the pair |
| Tuning gone after a respawn | appearance is not part of saved damage state | reapply from your vehicle row on spawn |
| Livery floats above or inside the roof | offset measured in world space | use `VEHICLE_MODEL_INFO_SIZE` and model-space offsets |
| Livery stays after the car explodes | attached object outlives the vehicle | destroy it in `OnVehicleDeath` and `OnVehicleSpawn` |
| Livery appears on another car | stray object reattached by vehicle id | same cleanup, keyed by vehicle id |

## Verification

No source file may reference the invented native, and the build must be clean:

```bash
grep -rn 'AddVehicleModel' qawno/include/ gamemodes/ | wc -l
pawncc gamemodes/main.pwn -ogamemodes/main.amx -d3 -(+ -;+ 2>&1 | grep -c 'error'
```

```text
0
0
```

Runtime proof that the look was applied to the model the server really has:

```pawn
printf("LOOK veh=%d model=%d paint=%d comp=%d", vehid, GetVehicleModel(vehid), GetVehiclePaintjob(vehid), GetVehicleComponentInSlot(vehid, CARMODTYPE_SPOILER));
```

```text
LOOK veh=12 model=560 paint=3 comp=0
```

`paint=3` means no paintjob is applied and `comp=0` means no spoiler survived, so re-apply on
spawn until the line matches the row you saved.

## Sources (2026)

- https://open.mp/docs/tags/custom-model
- https://open.mp/docs/scripting/functions/ChangeVehiclePaintjob
- https://open.mp/docs/scripting/functions/AttachObjectToVehicle
