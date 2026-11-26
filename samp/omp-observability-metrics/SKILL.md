---
name: omp-observability-metrics
description: Use when lag needs tick, player and query numbers.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, ops, monitoring, metrics]
    category: samp
---

# Observability and metrics

open.mp ships no metrics endpoint. What it does ship is four cheap numbers —
`GetServerTickRate()`, `GetPlayers()`, `CountRunningTimers()` and
`NetStats_PacketLossPercent()` — plus a log file. Emit them as one structured line and let
an external scraper do the rest; never do network I/O from the game thread.

## When to Use

- "The server lags" needs to become a number before anyone changes code.
- You are about to optimise and need a before/after window.
- A release went out and you need proof that tick rate did not regress.

## Compatibility & Stack Matrix (2026)

| Signal | Native | 2026 notes |
| --- | --- | --- |
| Tick rate | `GetServerTickRate()` | returns ticks per second, `0` right after start |
| Player count | `GetPlayers(ids, size)` | added 1.1.0.2612; returns count and fills the array |
| Player count (legacy) | `GetPlayerPoolSize()` | deprecated in RC2; do not use in new code |
| Live timers | `CountRunningTimers()` | added 1.1.0.2612 |
| Network totals | `GetNetworkStats(output, size)` | multi-line string, one line per counter |
| Per-player loss | `NetStats_PacketLossPercent(playerid)` | float, per player |
| Wall clock | `GetTickCount()` | wrap a query to time it |
| Tick budget | `sleep` config, default `5.0` | `1000 / 5 = 200` ticks per second |
| Tick smoothing | `use_dyn_ticks`, default `true` | holds the rate by burning CPU on catch-up |

## Production Implementation

1. Emit one line per 10 s, with fixed key order and no spaces inside values, so `awk -F=`
   can parse it years later:

```pawn
forward EmitMetrics();
public EmitMetrics()
{
    new ids[MAX_PLAYERS];
    new count = GetPlayers(ids, sizeof(ids));

    new Float:worst = 0.0;
    for (new i = 0; i < count; i++)
    {
        new Float:loss = NetStats_PacketLossPercent(ids[i]);
        if (loss > worst) worst = loss;
    }

    printf("METRIC tick=%d players=%d loss=%.1f timers=%d query_ms=%d",
        GetServerTickRate(), count, worst, CountRunningTimers(), g_LastQueryMs);
    return 1;
}
```

```pawn
public OnGameModeInit()
{
    SetTimer("EmitMetrics", 10000, true);
    return 1;
}
```

2. Time the slow dependency in the wrapper that already exists. Two `GetTickCount()` reads
   and one global — no plugin API change, works for any backend:

```pawn
new started = GetTickCount();
// the existing query / HTTP-cache / file read call goes here, unchanged
g_LastQueryMs = GetTickCount() - started;
```

3. Keep the metric line flat. `GetNetworkStats` returns a multi-line `key: value` block; it
   belongs in an admin dialog or a one-off console dump, never glued onto the metric line:

```bash
awk '/METRIC/ {print}' log.txt | tail -1
```

```text
METRIC tick=200 players=41 loss=0.3 timers=58 query_ms=7
```

4. Compute the window offline. Percentiles from the log, no server-side aggregation:

```bash
grep -o 'METRIC .*' log.txt | tail -120 | tr ' ' '\n' \
  | awk -F= '$1=="tick"{print $2}' | sort -n \
  | awk '{a[NR]=$1} END {printf "n=%d p50=%d p95=%d max=%d\n", NR, a[int(NR*0.5)], a[int(NR*0.95)], a[NR]}'
```

5. Alert on the trend, not the sample. At `sleep 5.0` the baseline is 200; p95 below 150 for
   five consecutive minutes with 30+ players is the page. One 180 tick line during a map
   load is not.

6. Watch the process too — tick rate can stay flat while RSS climbs. The pair is what
   separates a script leak from a network stall:

```bash
pid=$(pgrep -f omp-server | head -1)
ps -o rss=,etime= -p "$pid"
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Dashboard shows `tick=0` after every restart | `GetServerTickRate()` sampled before the first tick | skip samples with 0 and wait one interval |
| p95 collapses under load, CPU low | `sleep` raised above default | restore `sleep` to `5.0` unless the host is CPU-bound |
| CPU pinned at idle, tick flat | `use_dyn_ticks` burning cycles to hold 200 | set it false and accept a lower idle rate, or fix the hot loop |
| `players=` too high by exactly the NPC count | NPCs occupy player slots | subtract `max_bots` or count only connected humans |
| Parser breaks on one line a day | `GetNetworkStats` block printed inline | keep metrics one line; dump stats under its own prefix |
| Numbers cannot be tied to an incident | no timestamp on the metric | log `GetTickCount()` or rely on `logging.use_timestamp` |
| Log partition fills overnight | printing every tick | one line per 10 s, rotate weekly |
| Metrics stall during DDoS | metric emitted from an HTTP call in Pawn | emit to log, scrape from outside |

## Verification

Against a real log the percentile command prints a count and three integers:

```bash
grep -o 'METRIC .*' log.txt | tail -120 | tr ' ' '\n' \
  | awk -F= '$1=="tick"{print $2}' | sort -n \
  | awk '{a[NR]=$1} END {printf "n=%d p50=%d p95=%d max=%d\n", NR, a[int(NR*0.5)], a[int(NR*0.95)], a[NR]}'
```

```text
n=120 p50=198 p95=203 max=207
```

Then prove the signal moves: run a deliberately expensive command (a full inventory rebuild
for every online player) and re-run the same window.

```bash
grep -o 'METRIC .*' log.txt | tail -12 | tr ' ' '\n' | awk -F= '$1=="tick"{print $2}'
```

```text
171
168
174
169
```

A sustained drop in the tail window while `max` stays near 200 is the signature of a hot
path, not of a sampling artefact. Confirm memory did not move at the same time with
`ps -o rss= -p "$(pgrep -f omp-server | head -1)"`.

## Sources (2026)

- https://open.mp/docs/scripting/functions/GetServerTickRate
- https://open.mp/docs/scripting/functions/GetPlayers
- https://open.mp/docs/scripting/functions/GetNetworkStats
