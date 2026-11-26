---
name: state-machine-player-fsm
description: Use when player state is spread across loose booleans.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, architecture]
    category: samp
---

# One explicit state machine per player

## When to Use
- `pLogged`, `pSpawned`, `pAuthenticating` already contradict each other in production.
- `OnPlayerRequestClass`, `OnPlayerSpawn` or `OnDialogResponse` act on a player whose data is not loaded yet.
- You need to answer "what was this player doing when it broke?" from the log alone.

## Compatibility & Stack Matrix (2026)
| Component | Version | Notes |
| --- | --- | --- |
| pawncc | 3.10.10+ | `enum`, `switch`, 2-D `bool` tables; `-;+ -(+ -d3` |
| open.mp | 1.x | `OnPlayerStateChange` still means GTA state — do not reuse it for script state |
| SA-MP | 0.3.7-R5 | identical callbacks; player slots are recycled on reconnect |
| YSI y_iterate | 5.x | `foreach (new i : Player)` to walk live players for timeouts |
| crashdetect | 4.22+ | prints a stack trace; a global state dump makes it readable |

Model the lifecycle (connect → auth → play) as the machine. Keep `jailed`, `muted` and `dead` as orthogonal flags: putting them in the state enum multiplies the transition table and makes nonsensical combinations reachable.

## Production Implementation
1. Enumerate lifecycle states only, with `STATE_NONE = 0` so a zero-initialised array is valid.
2. Write the allowed transitions as a 2-D table indexed by `[from][to]`.
3. Route every write through one setter; nothing else may assign the variable.
4. Log refusals with player, from, to and reason — a silent rejection is unreviewable.
5. Keep exactly one documented bypass (`ForcePlayerState`) for disconnect, and grep for it in review.
6. Reset `gStateSince` on every accepted transition so stalled states can be reaped by a task.

```pawn
enum E_PLAYER_STATE
{
    STATE_NONE = 0,       // slot free, nothing loaded
    STATE_CONNECTING,     // OnPlayerConnect ran, data in flight
    STATE_AUTHENTICATING, // password dialog open
    STATE_PLAYING,        // data ready, may spawn and use commands
    STATE_LEAVING         // disconnect started, saves in flight
};

static const gTransition[E_PLAYER_STATE][E_PLAYER_STATE] =
{
    { false, true,  false, false, false }, // NONE
    { true,  false, true,  false, true  }, // CONNECTING
    { true,  false, false, true,  true  }, // AUTHENTICATING
    { true,  false, false, false, true  }, // PLAYING
    { true,  false, false, false, false }  // LEAVING
};

new E_PLAYER_STATE:gState[MAX_PLAYERS];
new gStateSince[MAX_PLAYERS];
```

```pawn
stock StateName(E_PLAYER_STATE:state)
{
    static const names[][] =
    {
        "NONE", "CONNECTING", "AUTHENTICATING", "PLAYING", "LEAVING"
    };
    return (state <= STATE_LEAVING) ? names[_:state] : "?";
}

stock SetPlayerState(playerid, E_PLAYER_STATE:to, const reason[])
{
    new E_PLAYER_STATE:from = gState[playerid];

    if (from == to) return 1;                        // idempotent: callbacks repeat
    if (!gTransition[from][to])
    {
        printf("[fsm] refused player=%d from=%s to=%s reason=%s",
            playerid, StateName(from), StateName(to), reason);
        return 0;
    }

    gState[playerid] = to;
    gStateSince[playerid] = gettime();
    printf("[fsm] player=%d %s -> %s (%s)",
        playerid, StateName(from), StateName(to), reason);
    return 1;
}

#define REQUIRE_STATE(%0,%1) if (gState[%0] != (%1)) return 0

stock ForcePlayerState(playerid, E_PLAYER_STATE:to, const reason[])
{
    new E_PLAYER_STATE:from = gState[playerid];

    gState[playerid] = to;
    gStateSince[playerid] = gettime();
    printf("[fsm] forced player=%d %s -> %s (%s)",
        playerid, StateName(from), StateName(to), reason);
    return 1;
}
```

```pawn
public OnPlayerRequestClass(playerid, classid)
{
    REQUIRE_STATE(playerid, STATE_PLAYING);   // 0 blocks class selection until data is ready
    SetPlayerPos(playerid, 1544.0, -1675.0, 13.5);
    return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
    SetPlayerState(playerid, STATE_LEAVING, "disconnect");
    QueuePlayerSave(playerid);                 // capture values before the slot is reused
    ForcePlayerState(playerid, STATE_NONE, "slot released");
    return 1;
}
```

## Failure Modes & Fixes
| Symptom | Cause | Fix |
| --- | --- | --- |
| dialog answers ignored | state moved to `PLAYING` before the dialog callback ran | only the data-load callback may move `AUTH -> PLAYING` |
| `refused ... PLAYING to PLAYING` spam | re-entrant callback | the `from == to` early return above |
| players stuck in `AUTHENTICATING` | no timeout | reap `gettime() - gStateSince` in a 5 s task |
| state `PLAYING` but money is zero | transitioned on connect instead of on load | transition inside the load callback |
| two features both "handle" death | death encoded as a state | keep `dead`/`jailed` as flags, not states |
| saves write the next player's row | forced reset ran before the save captured values | queue the save first, then force `NONE` |
| no trace after a crash | state only in a local variable | keep it in a global; crashdetect then shows the value |

## Verification
```bash
grep -rn "gState\[playerid\] *=" gamemodes/ | grep -v "fsm.inc"
```
Expected: no output — writes exist only in `SetPlayerState` and `ForcePlayerState` inside `fsm.inc`.

```bash
awk '/gTransition\[/,/^};/' gamemodes/fsm.inc | grep -c "true"
```
Expected: `10` — the table above has ten allowed edges. Adding a state without updating the count is visible in the diff.

Runtime: connect once and the log shows `[fsm] player=0 NONE -> CONNECTING (connect)` exactly once, followed by `CONNECTING -> AUTHENTICATING (dialog opened)`. A second connect on the same slot must not print `NONE -> CONNECTING` twice.

## Sources (2026)
- [YSI y_iterate quick start](https://raw.githubusercontent.com/pawn-lang/YSI-Includes/5.x/YSI_Data/y_foreach/quick-start.md) — `foreach (new i : Player)` for timeout sweeps.
- [YSI-Includes 5.x](https://github.com/pawn-lang/YSI-Includes) — include layout and library list used above.
- [open.mp documentation](https://open.mp/docs) — 2026 callback set; `OnPlayerStateChange` is GTA state, not script state.
