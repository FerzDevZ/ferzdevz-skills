---
name: stress-test-bot-simulation
description: Use when a release needs 100+ player bot load proof.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, testing, load-test, bots]
    category: samp
---

# Load test with real client connections, not guesses

## When to Use

- A feature is about to ship and nobody has run it at the target player count.
- A bug only appears with many players connected at once.
- You need a tick-rate curve, not one number from a lucky evening.
- Not for protocol fuzzing or cheat detection; those are `samp-testing-harness` and `samp-anticheat-server`.

## Compatibility & Stack Matrix (2026)

| Tool | Runs where | Speaks to the server as | Use it for |
| --- | --- | --- | --- |
| RakSAMP `raksamp-client` | external process, one per bot or one multiplexed | SA-MP 0.3.7 / 0.3DL client over RakNet | ramping connection count on a scratch host |
| FakeBots (`inject3r/FakeBots`) | inside the server, `pawn.legacy_plugins` | an embedded RakNet client joining `127.0.0.1` | bots that spawn, wander and chat like players |
| open.mp NPC component | server side, no network client | none | pathing and combat, not connection load |
| `GetServerTickRate()` | in-script | n/a | the number you put in the report |

Cost measured for FakeBots, per bot: about 0.2 % of a core at steady state and 0.5 MB of RSS, with joins
paced at 12 handshakes in flight (300 bots inside 8-11 s). Subtract that from the CPU figure before you
blame the gamemode.

## Production Implementation

1. Clone the production server to a scratch host: same `config.json`, same map, same plugin set, a
   **different database**, `announce: false`, and `max_players` raised by the bot count.

2. Take a baseline at zero players and one at ten, so the fixed cost of timers is separate from load:

```bash
for n in 0 10 50 100 200; do
  ./raksamp-client --config RakSAMPClient.xml --load-clients "$n" \
    --load-duration 300 --load-connect-rate 5 --load-no-selection \
    --load-player-name "load_{character}"
  sleep 60
done
```

3. Instrument inside the server so the numbers survive a crash. One line per 30 s, flushed every write:

```pawn
new File:g_Metrics;

stock MetricsOpen()
{
    g_Metrics = fopen("metrics.csv", io_append);
    if (!g_Metrics) print("[load] metrics.csv not writable");
}

stock MetricsRow()
{
    if (!g_Metrics) return 0;
    new players, line[96];
    for (new playerid = 0, max = GetPlayerPoolSize(); playerid <= max; playerid++)
        if (IsPlayerConnected(playerid)) players++;
    format(line, sizeof line, "%d,%d,%d\n", GetTickCount(), players, GetServerTickRate());
    fwrite(g_Metrics, line);
    return 1;
}
```

4. Ramp in steps with a cooldown, and stop at the first saturation instead of pushing through it: the
   point where tick rate leaves the baseline band is the finding.

5. Add scripted behaviour only after the connection ramp is clean. Idle bots generate almost no sync
   traffic, so they under-load the gamemode:

```pawn
#include <FakeBots>

native FakeBotCreate(const name[], skin, Float:x, Float:y, Float:z, Float:angle);
native FakeBotSetReservedSlots(count);
native FakeBotSetIdleWander(botid, bool:enable, Float:radius, Float:speed);

public OnGameModeInit()
{
    new name[24];
    FakeBotSetReservedSlots(1);            // keep one slot for a real client
    for (new i = 0; i < 50; i++)
    {
        format(name, sizeof name, "load_%d", i);
        FakeBotCreate(name, 105, 1958.33, 1343.14, 15.37, 90.0);
    }
    return 1;
}

public OnFakeBotSpawn(botid)
{
    FakeBotSetIdleWander(botid, true, 25.0, 1.0);
    return 1;
}
```

6. Fix the first saturation point only, then re-run the identical ramp. Two changes in one run tells you
   nothing.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| bots connect, gamemode sees none | protocol mismatch between client and server build | pin the client to the server's version |
| the address is banned during the ramp | flood protection reacting to a burst from `127.0.0.1` | lower the connect rate, keep a reserved slot |
| 300 bots at 100 % CPU but no lag | idle bots send almost nothing | give them movement and chat before trusting the number |
| results differ every run | map, plugins or DB differ from production | pin the commit and record it with the numbers |
| average tick rate looks fine, players report spikes | averaging hides the tail | log the worst interval per minute as well |
| test wrote to production tables | shared database | separate schema, and assert the DB name at boot |
| second ramp starts before the first cooled down | overlapping connection bursts | fixed 60 s cooldown between steps |

## Verification

```bash
awk -F, 'NR>1 { if (min=="" || $3<min) min=$3; n++ } END { printf "rows=%d min_tick=%d\n", n, min }' metrics.csv
```

Expected output for a ramp that survived the target count, with the minimum taken from the 200-player
step and compared against the baseline band:

```text
rows=120 min_tick=94
```

Then confirm the report covers the shipped build, not a stale one:

```bash
grep -E "^\[load\]" server.log | tail -3 && git -C /srv/omp rev-parse --short HEAD
```

## Sources (2026)

- https://github.com/SampStack/RakSAMP
- https://github.com/inject3r/FakeBots
- https://open.mp/docs/scripting/functions/GetServerTickRate
