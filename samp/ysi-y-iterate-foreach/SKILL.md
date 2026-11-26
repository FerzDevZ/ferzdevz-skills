---
name: ysi-y-iterate-foreach
description: Use when a player loop scans empty slots every tick.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi]
    category: samp
---

# foreach and custom iterators

## When to Use

- A per-tick loop runs `for (new i = 0; i < MAX_PLAYERS; i++)` and calls natives for 1000 slots when
  nine players are connected.
- A second loop over the same pool hides inside a command and doubles the tick cost.
- You keep a list of "active" vehicles, races or houses in a manually maintained array with a `used[]`
  flag.
- A stale id is processed after the entity was destroyed, because the array was never compacted.
- You want the connected count without a second pass over the pool.

## Compatibility & Stack Matrix (2026)

| Item | Version | Notes |
| --- | --- | --- |
| YSI | 5.x | include `YSI_Data\y_iterate` (also published as `y_foreach`) |
| Pawn loop cost | any | plain pool loop is O(MAX_PLAYERS); `foreach` is O(connected) |
| Built-in iterators | `Player`, `Vehicle` | maintained by YSI's own hooks, not by your code |
| Custom iterator | `Iterator:Name<limit>` | values added must be `0 .. limit-1` |
| Add / remove | `Iter_Add`, `Iter_Remove` | `Iter_Add` on a value already present does not duplicate it |
| Count / membership | `Iter_Count`, `Iter_Contains` | `Iter_Count(Player)` replaces a manual count loop |
| Structure | sparse set | a value present once, removed in O(1), no `used[]` parallel array |

YSI's own description: for players this is "constant time O(n) for number of connected players", while
a standard loop is O(MAX_PLAYERS) "regardless of the actual number of connected players".

## Production Implementation

1. Include the public header and delete the pool loops. `Player` already contains exactly the connected
   players, so `IsPlayerConnected` inside the body is redundant:

```pawn
#include <YSI_Data\y_iterate>

public OnPlayerTick()
{
    foreach (new i : Player)
    {
        SendClientMessage(i, 0xFFFFFFFF, "tick");
    }
    return 1;
}
```

2. Give every hand-maintained list its own iterator with the right limit. A limit that is too small
   rejects the value silently, so size it from the pool constant:

```pawn
new Iterator:gRaceVehicles<MAX_VEHICLES>;

stock TrackVehicle(vid)
{
    if (!IsValidVehicle(vid)) return 0;
    Iter_Add(gRaceVehicles, vid);
    return 1;
}

stock UntrackVehicle(vid)
{
    Iter_Remove(gRaceVehicles, vid);
    return 1;
}
```

3. Keep the iterator and the entity lifetime in one place. Add on create, remove before destroy — never
   the other way round, or a recycled id re-enters the list on its own:

```pawn
stock SpawnRaceVehicle(model, Float:x, Float:y, Float:z)
{
    new vid = CreateVehicle(model, x, y, z, 0.0, 0, 0, -1);
    TrackVehicle(vid);
    return vid;
}

stock KillRaceVehicle(vid)
{
    UntrackVehicle(vid);      // first
    DestroyVehicle(vid);      // then
    return 1;
}
```

4. Do not remove the current element inside `foreach`. Collect the ids, then remove after the loop:

```pawn
stock ClearRace()
{
    new ids[MAX_VEHICLES], n;
    foreach (new vid : gRaceVehicles) ids[n++] = vid;
    for (new i = 0; i < n; i++) KillRaceVehicle(ids[i]);
    return 1;
}
```

5. Use `Iter_Count` when you only need a size, and `Iter_Contains` before acting on an id that may have
   been removed by another system:

```pawn
printf("tracked vehicles: %d", Iter_Count(gRaceVehicles));
if (Iter_Contains(gRaceVehicles, vid)) KillRaceVehicle(vid);
```

6. Keep the built-in iterators trustworthy. `Player` and `Vehicle` are maintained by YSI's connect,
   disconnect and create hooks, so re-adding them yourself double-counts in the best case and hides a
   real bug in the worst.

7. Benchmark the change instead of assuming it. One loop over 1000 slots with a native call per slot is
   visible in a profiled tick; `foreach` over nine players is not.

```pawn
stock CountConnected()
{
    return Iter_Count(Player);
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `undefined symbol "foreach"` at compile | header not included, or wrong path | `#include <YSI_Data\y_iterate>` and check `-i./includes` |
| Custom iterator misses entities | nobody called `Iter_Add` on create | add at the single creation path |
| Destroyed vehicle still handled | removed after destroy, id recycled | `Iter_Remove` before `DestroyVehicle` |
| One entity handled twice in a pass | value added twice from two code paths | `Iter_Add` is idempotent; find the duplicate caller instead |
| `Iter_Add` returns nothing useful for high ids | value `>= limit` is rejected | size the iterator from `MAX_VEHICLES`/`MAX_PLAYERS` |
| Loop skips an element after a removal | removal inside `foreach` | collect ids, remove after the loop |
| No speed-up at all | the real cost is the native inside the body, not the loop | profile the body, not the iteration |

## Verification

```bash
pawncc -i./includes -d3 -ogamemodes/main.amx gamemodes/main.pwn && echo "foreach compiled"
grep -n 'i < MAX_PLAYERS' gamemodes/*.pwn || echo "no pool loops left"
```

Expected output — the include resolves, and no hand-rolled player loop survived the refactor:

```text
foreach compiled
no pool loops left
```

Then compare the two counts at runtime; they must match exactly, including NPC slots:

```pawn
printf("connected=%d iter=%d", CountConnected(), Iter_Count(Player));
```

```text
connected=12 iter=12
```

## Sources (2026)

- https://github.com/pawn-lang/YSI-Includes/blob/5.x/YSI_Data/y_foreach/api.md
- https://github.com/pawn-lang/YSI-Includes/blob/5.x/YSI_Data/y_foreach/quick-start.md
- https://github.com/pawn-lang/YSI-Includes
