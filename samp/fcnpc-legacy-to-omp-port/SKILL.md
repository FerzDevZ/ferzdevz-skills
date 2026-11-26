---
name: fcnpc-legacy-to-omp-port
description: Use when FCNPC calls must move to open.mp NPC natives.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, npc, migration]
    category: samp
---

# Port FCNPC to the component that replaced it

open.mp ships an NPC component, `components/NPCs.so`, and its installation guide
says the legacy FCNPC plugin "has been replaced with the official open.mp NPC
component". The native names changed (`FCNPC_*` to `NPC_*`), the callbacks changed
(`FCNPC_OnSpawn` to `OnNPCSpawn`), and the plugin must be deleted, not kept next
to the component. Load both and you get duplicate symbols or a server that
silently ignores half the calls.

## When to Use

- A 0.3.7 gamemode includes `fcnpc.inc` or loads `FCNPC.so`.
- A server updated to open.mp 1.5.8 or newer and NPCs stopped spawning.
- Callbacks fire for players but never for bots.
- You are writing new bot code and need to know which API is current.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp ≥ 1.5.8.3079 | `NPC_Create` was added in 1.5.8.3079; older builds have no NPC_* API |
| Component | `components/NPCs.so` | ships in the release tarball, loaded automatically |
| Include | `#include <open.mp>` | `omp_npc` is pulled in by the main include |
| Limits | `MAX_NPCS` 1..1000 | default 1000, compile-time override |
| Config | `max_bots`, `npc.*` sync rates | `max_bots: 0` blocks every NPC from spawning |
| Legacy | FCNPC plugin + `fcnpc.inc` | delete both; do not run them beside the component |

## Production Implementation

1. Delete the plugin before touching code. A leftover `FCNPC.so` in `plugins/`
   plus the component gives you two implementations of the same natives.

```bash
rm -f plugins/FCNPC.so
grep -rn "FCNPC\|fcnpc" gamemodes/ | tee /tmp/fcnpc-hits.txt | wc -l
sed -i '/#include <fcnpc>/d' gamemodes/*.pwn
```

2. Map the calls. Signatures mostly line up, but `SetPosition` becomes `SetPos`
   and the record API gained an explicit start call.

| FCNPC (0.3.7 plugin) | open.mp component | Note |
| --- | --- | --- |
| `FCNPC_Create(name[])` | `NPC_Create(name[])` | returns `INVALID_NPC_ID` on failure |
| `FCNPC_Destroy(npcid)` | `NPC_Destroy(npcid)` | |
| `FCNPC_Spawn(npcid)` | `NPC_Spawn(npcid)` | still required after create |
| `FCNPC_Respawn(npcid)` | `NPC_Respawn(npcid)` | |
| `FCNPC_IsValid(npcid)` | `NPC_IsValid(npcid)` | |
| `FCNPC_SetPosition(...)` | `NPC_SetPos(...)` | also `FCNPC_GetPosition` → `NPC_GetPos` |
| `FCNPC_SetAngle` / `GetAngle` | `NPC_SetRot` / `NPC_GetRot` | |
| `FCNPC_Move` / `StopMove` | `NPC_Move` / `NPC_StopMove` | move type enum differs |
| `FCNPC_SetHealth` / `GetHealth` | `NPC_SetHealth` / `NPC_GetHealth` | |
| `FCNPC_SetWeapon` / `SetAmmo` | `NPC_SetWeapon` / `NPC_SetAmmo` | |
| `FCNPC_AimAtPlayer` / `Shoot` | `NPC_AimAtPlayer` / `NPC_Shoot` | |
| `FCNPC_IsDead` | `NPC_IsDead` | |
| `FCNPC_LoadRecord` / `FCNPC_Play` | `NPC_LoadRecord` / `NPC_StartPlayback` | load once, start per NPC |

3. Rewrite the spawn helper. `NPC_Create` does not spawn; `NPC_Spawn` does, and a
   create that fails returns `INVALID_NPC_ID` rather than a negative index.

```pawn
stock CreateGuard(const name[], Float:x, Float:y, Float:z)
{
    new npcid = NPC_Create(name);
    if (!NPC_IsValid(npcid)) return INVALID_NPC_ID;

    NPC_Spawn(npcid);
    NPC_SetPos(npcid, x, y, z);
    NPC_SetHealth(npcid, 100.0);
    NPC_SetWeapon(npcid, WEAPON_M4);
    NPC_SetAmmo(npcid, 500);
    return npcid;
}
```

4. Replace the callbacks. The omp versions are `OnNPCCreate`, `OnNPCDestroy`,
   `OnNPCSpawn`, `OnNPCDeath(npcid, killerid, WEAPON:reason)` and
   `OnNPCTakeDamage(npcid, issuerid, Float:amount, WEAPON:weaponid, bodypart)`.

```pawn
public OnNPCSpawn(npcid)
{
    NPC_SetFightingStyle(npcid, FIGHT_STYLE_NORMAL);
    return 1;
}

public OnNPCDeath(npcid, killerid, WEAPON:reason)
{
    g_GuardCount--;
    return 1;
}
```

5. Keep NPC ids in their own array. An `npcid` is not a `playerid`; storing both
   in one `MAX_PLAYERS` array is how bots start receiving player dialogs.

```pawn
new g_Guard[MAX_NPCS];
g_Guard[0] = CreateGuard("Guard_01", 1481.0, -1770.0, 18.8);
```

6. Check the config before debugging code: `max_bots` must be greater than zero,
   or `NPC_Spawn` does nothing and no callback fires.

```json
{
  "max_bots": 32,
  "npc": { "process_update_rate": 50, "on_foot_sync_rate": 30 }
}
```

7. Test the three behaviours that used to come from the plugin: pathing,
   combat and death. Pathing needs a path or a record; a bot with neither will
   stand still and look like a failed port.

```bash
docker compose logs --no-color omp | grep -E 'OnNPCSpawn|OnNPCDeath|NPC'
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `error 017: undefined symbol "FCNPC_Create"` | include removed, calls not migrated | map every call from the table above |
| `NPC_Create` undefined at compile time | server/stdlib older than 1.5.8.3079 | update the server and the `omp-stdlib` include together |
| Bots never spawn and no callback fires | `max_bots` is `0` | set `max_bots` above the number of bots you create |
| Both NPC systems loaded, random behaviour | `FCNPC.so` still in `plugins/` | delete the plugin file and restart |
| `OnNPCDeath` never called | callback still named `FCNPC_OnDeath` | rename to `OnNPCDeath` with the `WEAPON:` tag |
| Bots spawn but never move | no path, node or record loaded | `NPC_CreatePath`/`NPC_MoveByPath` or `NPC_LoadRecord` + `NPC_StartPlayback` |

## Verification

```bash
grep -rn "FCNPC" gamemodes/ scripts/ && echo "legacy calls remain" || echo "no FCNPC calls"
pawncc -i$HOME/samp-sdk/omp-stdlib -d3 '-;+' '-(' gamemodes/bots.pwn -obots.amx
docker compose logs --no-color omp | grep -c "OnNPCSpawn"
```

- `no FCNPC calls` and a clean `pawncc` run with zero diagnostics.
- `OnNPCSpawn` count matches the number of bots you create in `OnGameModeInit`.
- A bot takes damage and dies, and `OnNPCDeath` fires once per death.

## Sources (2026)

- https://open.mp/docs/server/Installation
- https://open.mp/docs/scripting/functions/NPC_Create
- https://github.com/openmultiplayer/omp-stdlib/blob/master/omp_npc.inc
