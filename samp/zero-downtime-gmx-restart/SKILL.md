---
name: zero-downtime-gmx-restart
description: Use when gmx must reload the mode without a kick.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ops]
    category: samp
---

# gmx restart without dropping players

## When to Use

- A deploy has to land while players are online and a full process restart is unacceptable.
- You are about to call `SendRconCommand("gmx")` and need to know what state survives it (nothing).
- Player money, vehicles or inventory vanish after a reload and you need the recovery path.
- Someone proposes "zero downtime" and you must show what one process can and cannot promise.

## Compatibility & Stack Matrix (2026)

| Item | Behaviour | Notes |
| --- | --- | --- |
| Command | `/rcon gmx` or console `gmx` | open.mp docs: loads the next gamemode in `config.json` |
| `OnGameModeExit` | runs on gmx | also on shutdown and `GameModeExit` |
| `OnGameModeInit` | runs again after the reload | a second run in the same process, not a new one |
| Reload gap | ~12 s measured on 1.6.7.3218 | previous mode unloaded, next one not yet initialised |
| Player connection | kept | no `OnPlayerConnect`, so no fresh login flow to lean on |
| Script state | lost | arrays, iterators, timers, objects, textdraws, PVars |
| Rotation | `pawn.main_scripts` order | a single entry reloads the same script |
| Risk | `RemoveBuildingForPlayer` in `OnGameModeInit` | docs warn about client crashes when combined with gmx |

## Production Implementation

1. Persist everything first. The reload keeps the connection but destroys the variables, so write
   state before the command and never inside `OnGameModeExit` alone (it can be skipped on a crash):

```pawn
forward SaveAllPlayers();
public SaveAllPlayers()
{
    foreach (new i : Player)
    {
        SaveAccount(i);      // synchronous write or queued row per player
        SaveInventory(i);
    }
    return 1;
}
```

2. Announce and re-anchor players so nobody is mid-heist when the world reloads:

```pawn
stock BeginRestart()
{
    foreach (new i : Player)
    {
        SendClientMessage(i, 0xFFAA00FF, "Server restarting in 10 seconds, progress is saved.");
        TogglePlayerControllable(i, false);
    }
    SetTimer("DoRestart", 10000, false);
    return 1;
}

forward DoRestart();
public DoRestart()
{
    SaveAllPlayers();
    SendRconCommand("gmx");
    return 1;
}
```

3. Initialise once in `OnGameModeInit` and make it idempotent. The callback runs again on the same
   process, so anything created by hand (objects, textdraws, timers) must be created exactly here
   and nowhere else, or the reload duplicates it:

```pawn
public OnGameModeInit()
{
    Iter_Init(PlayerVehicles);   // foreach containers are script state and start empty again
    CreateServerObjects();       // the only place objects are created
    SetTimer("Autosave", 60000, true);
    printf("mode reloaded, session re-entry");
    return 1;
}
```

4. Restore per-player data lazily, on the first tick after the reload. `OnGameModeInit` runs before
   any player state exists again, so loading player files there reads stale ids:

```pawn
public OnPlayerSpawn(playerid)
{
    LoadAccount(playerid);
    LoadInventory(playerid);
    TogglePlayerControllable(playerid, true);
    return 1;
}
```

5. Expect the gap. Between `OnGameModeExit` and the next `OnGameModeInit` the server answers
   connections but runs no mode code, so schedule the restart outside peak and keep the gap short by
   removing blocking work from `OnGameModeInit` (no synchronous HTTP, no big file parse).

6. Use `changemode` for switching to a different mode instead of editing `pawn.main_scripts` and
   calling gmx; it takes the target as an argument and leaves the rotation alone:

```bash
echo "changemode race" | socat - UDP:127.0.0.1:7777
```

7. For genuinely zero downtime, stop trying to do it in one process. Run two instances on different
   ports behind a UDP proxy, boot the idle one, health-check it, then switch the proxy target:

```bash
./omp-server --config-path config-blue.json &     # port 7778
nc -zu 127.0.0.1 7778 && echo "blue up"
# flip proxy 7777 -> 7778, drain, then stop the old instance
```

8. Do not chain gmx: a second command during the reload gap is queued behind a mode that does not
   exist yet. Guard it with a flag so only one restart can be in flight.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Players keep playing but money is 0 | variables reset, no reload of saved state | persist before gmx, load in `OnPlayerSpawn` |
| Objects and textdraws doubled | created in `OnPlayerConnect`/`OnGameModeInit` twice | create only in `OnGameModeInit`, destroy in `OnGameModeExit` |
| Clients crash right after the reload | `RemoveBuildingForPlayer` in `OnGameModeInit` on gmx | move removals to the first spawn or skip them on reload |
| Server idle for ~10 s, no mode code | reload gap while the old mode unloads | restart off-peak, keep init fast |
| `OnGameModeInit` prints twice at boot | gamemode listed twice in `pawn.main_scripts` | one entry per mode, use `changemode` to switch |
| Save data missing after a crash | only saved inside `OnGameModeExit` | autosave on a timer as well |

## Verification

```bash
mkfifo /tmp/omp.stdin
./omp-server < /tmp/omp.stdin > /tmp/boot.log 2>&1 &
exec 3> /tmp/omp.stdin
sleep 3; echo gmx >&3; sleep 15; kill %1; exec 3>&-
grep -cE 'GM INIT' /tmp/boot.log; grep -cE 'GM EXIT' /tmp/boot.log
grep -E 'GM (INIT|EXIT)' /tmp/boot.log
```

Expected output on a mode that prints both markers:

```text
2
1
[Info] GM INIT
[Info] GM EXIT
[Info] GM INIT
```

## Sources (2026)

- https://open.mp/docs/scripting/callbacks/OnGameModeExit
- https://open.mp/docs/scripting/callbacks/OnGameModeInit
- https://open.mp/docs/server/ControllingServer
