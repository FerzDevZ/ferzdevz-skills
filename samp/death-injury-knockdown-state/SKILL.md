---
name: death-injury-knockdown-state
description: Use when death, injury and knockdown double-fire.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, combat]
    category: samp
---

# Four combat states, one owner of the death event

## When to Use

- Players die instantly where the design says "downed, then bleed out".
- `OnPlayerDeath` runs the hospital code twice, or counts a kill for an already dead player.
- A knockdown survives respawn: the player spawns unable to move.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | `OnPlayerDeath`/`OnPlayerSpawn` order unchanged from SA-MP 0.3.7-R5 |
| health read | integer-rounded | set 50.15, read back 50.0, so the guard polls a threshold |
| control lock | `TogglePlayerControllable` | client-side; fire and vehicle entry still need guards |
| timers | `SetTimerEx` per player | one id per concern, killed on spawn, death and revive |

## Production Implementation

1. Four states only: `ALIVE`, `DOWN` (controls locked), `INJURED` (mobile, bleeding), `DEAD`. Lifecycle states belong to the FSM skill, and a non-lethal knockdown is just `CombatDown` with `CST_ALIVE` as the return state.
2. Enter `DOWN` from a health guard *before* zero, so the client never renders a death that the script then undoes.
3. Let `OnPlayerDeath` produce `CST_DEAD` exactly once, guarded against a duplicate callback; the guard already converted every gradual death into downtime.
4. Cancel timers before every phase change, and reset the whole block in `OnPlayerSpawn` — this is the module:

```pawn
enum E_COMBAT_STATE { CST_ALIVE = 0, CST_DOWN, CST_INJURED, CST_DEAD };
#define INJURE_HP    (25.0)
#define REVIVE_HP    (50.0)
#define DOWN_MS      (2500)
#define BLEEDOUT_MS  (30000)

new E_COMBAT_STATE:gCombat[MAX_PLAYERS], gDownReturn[MAX_PLAYERS];
new gTimer[MAX_PLAYERS][3] = {{-1, -1, -1}, ...};   // 0 get-up, 1 bleed-out, 2 guard
new gDeathCount[MAX_PLAYERS];
static const gCombatNames[][8] = { "ALIVE", "DOWN", "INJURED", "DEAD" };

stock CombatSet(playerid, E_COMBAT_STATE:to, const why[])
{
    new E_COMBAT_STATE:from = gCombat[playerid];
    if (from == to) return 0;
    gCombat[playerid] = to;
    printf("[combat] player=%d %s->%s (%s)", playerid, gCombatNames[_:from], gCombatNames[_:to], why);
    return 1;
}

stock CombatClearTimers(playerid)
{
    for (new i = 0; i < 3; i++)
        if (gTimer[playerid][i] != -1) { KillTimer(gTimer[playerid][i]); gTimer[playerid][i] = -1; }
}

stock CombatDown(playerid, E_COMBAT_STATE:back, const why[])
{
    gDownReturn[playerid] = back;
    TogglePlayerControllable(playerid, false);
    CombatSet(playerid, CST_DOWN, why);
    gTimer[playerid][0] = SetTimerEx("CombatGetUp", DOWN_MS, false, "i", playerid);
    gTimer[playerid][1] = SetTimerEx("CombatBleedOut", BLEEDOUT_MS, false, "i", playerid);
    return 1;
}

forward CombatGuard(playerid);
public CombatGuard(playerid)
{
    if (gCombat[playerid] != CST_ALIVE) return 1;
    new Float:hp;
    GetPlayerHealth(playerid, hp);
    if (hp > INJURE_HP) return 1;
    SetPlayerHealth(playerid, INJURE_HP);        // clamp once, then damage applies again
    return CombatDown(playerid, CST_INJURED, "health below threshold");
}

public OnPlayerDeath(playerid, killerid, reason)
{
    gDeathCount[playerid]++;
    CombatClearTimers(playerid);
    if (gCombat[playerid] == CST_DEAD) return 1;             // duplicate callback
    CombatSet(playerid, CST_DEAD, "lethal hit while alive or downed");
    printf("[combat] death player=%d killer=%d reason=%d count=%d", playerid, killerid, reason, gDeathCount[playerid]);
    return 1;
}

forward CombatGetUp(playerid);
public CombatGetUp(playerid)
{
    gTimer[playerid][0] = -1;
    if (gCombat[playerid] != CST_DOWN) return 1;
    TogglePlayerControllable(playerid, true);
    return CombatSet(playerid, gDownReturn[playerid], "got up");
}

forward CombatBleedOut(playerid);
public CombatBleedOut(playerid)
{
    gTimer[playerid][1] = -1;
    if (gCombat[playerid] != CST_INJURED && gCombat[playerid] != CST_DOWN) return 1;
    printf("[combat] player=%d bled out", playerid);
    SetPlayerHealth(playerid, 0.0);   // the only voluntary kill in this module
    return 1;
}

stock CombatRevive(playerid)
{
    CombatClearTimers(playerid);      // kill the bleed-out before healing
    SetPlayerHealth(playerid, REVIVE_HP);
    TogglePlayerControllable(playerid, true);
    return CombatSet(playerid, CST_ALIVE, "revived");
}

public OnPlayerSpawn(playerid)
{
    CombatClearTimers(playerid);
    gCombat[playerid] = CST_ALIVE;
    gTimer[playerid][2] = SetTimerEx("CombatGuard", 250, true, "i", playerid);
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| hospital code runs twice per death | `OnPlayerDeath` not guarded, reached from two scripts | `CST_DEAD` check plus a per-player counter |
| player spawns unable to move | get-up timer from the previous life still armed | `CombatClearTimers` at the top of `OnPlayerSpawn` |
| revive kills the player a second later | bleed-out timer not killed before healing | kill timers, then `SetPlayerHealth` |
| injured player is invincible | health re-clamped every tick above incoming damage | guard returns early unless state is `ALIVE` |
| health flickers around 25 | comparing the rounded read-back to a float | clamp once to `INJURE_HP`, do not re-clamp |

## Verification

```bash
grep -c "SetPlayerHealth(playerid, 0.0)" gamemodes/combat.pwn; grep -c "SetTimerEx(\"CombatGuard\"" gamemodes/combat.pwn
```

Expected: `1` then `1` — one voluntary kill (bleed-out) and one guard timer. A second `0.0` line is a bypass.

Runtime trace for a guard downing followed by a bleed-out, in order:

```text
[combat] player=3 ALIVE->DOWN (health below threshold)
[combat] player=3 DOWN->INJURED (got up)
[combat] player=3 bled out
[combat] player=3 INJURED->DEAD (lethal hit while alive or downed)
[combat] death player=3 killer=7 reason=24 count=1
```

`count=2` on one death, or a `DOWN` line after `DEAD`, means the guard or the timer cleanup is wrong.

## Sources (2026)

- [open.mp — OnPlayerDeath](https://open.mp/docs/scripting/callbacks/OnPlayerDeath) — parameters, `INVALID_PLAYER_ID` killer, weapon id as `reason`.
- [open.mp — SetPlayerHealth](https://open.mp/docs/scripting/functions/SetPlayerHealth) — 0.0 kills instantly, value read back rounded.
