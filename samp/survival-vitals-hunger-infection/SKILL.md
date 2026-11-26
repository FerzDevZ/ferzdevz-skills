---
name: survival-vitals-hunger-infection
description: Use when hunger, thirst or infection drift and pile up.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, gameplay, timers, survival]
    category: samp
---

# One global tick, millisecond accumulators, hard clamps

Vitals are cheap arithmetic and expensive timers. One repeating timer walks the player list
once per second, and a player's next point of hunger is due when their accumulator has held
enough milliseconds, so a stutter does not starve anyone twice.

## When to Use

- Hunger or thirst drains faster the longer the server has been up.
- Vitals reset on respawn, or survive a respawn they should not.
- Coughing, damage or messages fire every tick at a threshold.

## Compatibility & Stack Matrix (2026)

| Layer | 2026 baseline | Note |
| --- | --- | --- |
| Server | open.mp 1.6.x | `SetTimer` intervals are accurate; SA-MP drifted up to ~25% |
| Timer | one `SetTimer("Vitals_Tick", 1000, true)` | id kept so `OnGameModeExit` can kill it |
| Vitals | 0-100 integer points | clamped in one stock, never decremented below 0 |
| Health | `GetPlayerHealth`, `SetPlayerHealth` | damage floored at 5.0 so vitals never kill |

## Production Implementation

1. Declare intervals in milliseconds, not as "per tick" amounts, so the tick length can change
   without retuning gameplay:

```pawn
#define VITALS_TICK_MS   1000
#define HUNGER_DECAY_MS  40000      // one point of hunger every 40 s
#define INFECT_GAIN_MS   60000      // one point of infection every 60 s while weakened
#define DAMAGE_EVERY_MS  5000

new g_Hunger[MAX_PLAYERS], g_Infection[MAX_PLAYERS];
new g_HungerAcc[MAX_PLAYERS], g_InfectAcc[MAX_PLAYERS];
new g_DamageAcc[MAX_PLAYERS], g_Stage[MAX_PLAYERS];
new g_VitalsTimer, g_LastTick;
new bool:g_VitalsLoaded[MAX_PLAYERS];
```

2. Clamp once in a stock that every writer calls, and drain whole intervals through one helper:

```pawn
stock Vitals_Clamp(&value, min = 0, max = 100)
{
    if (value < min) value = min;
    else if (value > max) value = max;
    return value;
}

stock Vitals_Drain(&value, &acc, elapsed, interval)
{
    if (value <= 0) return 0;
    acc += elapsed;
    while (acc >= interval) acc -= interval, Vitals_Clamp(--value);
    return 1;
}
```

3. Start one timer in `OnGameModeInit` and keep its id; no `SetTimerEx` in connect, spawn or any
   command. The stored id is what lets `gmx` stop cleanly:

```pawn
public OnGameModeInit()
{
    g_LastTick = GetTickCount();
    g_VitalsTimer = SetTimer("Vitals_Tick", VITALS_TICK_MS, true);
    return 1;
}
```

4. Take the real elapsed time each tick and discard a nonsense delta, so a tick arriving 30
   seconds late (map load, blocking query) cannot drain 30 seconds at once:

```pawn
forward Vitals_Tick();
public Vitals_Tick()
{
    new now = GetTickCount(), elapsed = now - g_LastTick;
    g_LastTick = now;
    if (elapsed <= 0 || elapsed > 5000) elapsed = VITALS_TICK_MS;

    for (new p; p < MAX_PLAYERS; p++)
        if (IsPlayerConnected(p) && !IsPlayerNPC(p))
            Vitals_Step(p, elapsed);
    return 1;
}

stock Vitals_Step(playerid, elapsed)
{
    Vitals_Drain(g_Hunger[playerid], g_HungerAcc[playerid], elapsed, HUNGER_DECAY_MS);
    if (g_Hunger[playerid] < 25)
        Vitals_Drain(g_Infection[playerid], g_InfectAcc[playerid], elapsed, INFECT_GAIN_MS);
    return Vitals_Effects(playerid, elapsed);
}
```

5. Gate every effect on a transition or a cadence, never on "the value is low":

```pawn
stock Vitals_Effects(playerid, elapsed)
{
    new stage = (g_Infection[playerid] >= 85) ? 3 : (g_Infection[playerid] >= 25) ? 1 : 0;
    if (stage != g_Stage[playerid])
        g_Stage[playerid] = stage, SendClientMessage(playerid, 0xFFAA00FF, "You feel feverish.");
    if (g_Hunger[playerid] > 0 && stage < 3) return (g_DamageAcc[playerid] = 0), 1;
    g_DamageAcc[playerid] += elapsed;
    if (g_DamageAcc[playerid] < DAMAGE_EVERY_MS) return 1;

    new Float:health;
    g_DamageAcc[playerid] = 0;
    GetPlayerHealth(playerid, health);
    if (health > 5.0) SetPlayerHealth(playerid, health - 2.0);
    return 1;
}
```

6. Kill the timer in `OnGameModeExit` with the stored id, reset on spawn only when the account
   did not supply values, and clear `g_Stage` and `g_DamageAcc` unconditionally or a death
   carries the old stage into the next life (see `async-player-data-load-save`).

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Hunger drains faster the longer the server runs | per-tick decrement instead of elapsed accumulation | accumulate `elapsed`, drain whole intervals |
| Server hitches every second | one `SetTimerEx` per player | one global timer looping the player list |
| Vitals keep draining after `gmx` | timer id discarded, never killed | keep the id, `KillTimer` in `OnGameModeExit` |
| Threshold message spams chat | effect applied on value, not on transition | compare against the previous stage |

## Verification

The timer shape is the gate — one `SetTimer`, no per-player timer anywhere:

```bash
grep -rn "SetTimerEx" gamemodes/vitals.pwn ; echo "timer_exit=$?"
grep -c 'SetTimer("Vitals_Tick", VITALS_TICK_MS, true)' gamemodes/*.pwn
```

Expected `timer_exit=1` from the first (no match) and `1` from the second. Then prove the decay
maths cannot drift by running the same loop for an hour:

```bash
python3 -c "h=100;a=0
for _ in range(3600):
    a+=1000
    while a>=40000: a-=40000;h=max(0,h-1)
print('hunger_after_1h',h,'remainder_ms',a)"
```

```text
hunger_after_1h 10 remainder_ms 0
```

Ninety points in 3600 seconds is exactly `3600000 / 40000`; anything else means the accumulator is wrong.

## Sources (2026)

- https://open.mp/docs/scripting/functions/SetTimer — interval, `repeating`, ids from 1, `INVALID_TIMER`, and the note that open.mp fixed SA-MP's timer drift.
- https://open.mp/docs/scripting/functions/SetPlayerHealth — health is a float clamped to the 0-100 client range.
