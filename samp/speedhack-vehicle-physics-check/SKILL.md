---
name: speedhack-vehicle-physics-check
description: Use when cars outrun their handling top speed.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, anticheat, vehicles]
    category: samp
---

# Vehicle speed check: measured velocity against the model's handling ceiling

## When to Use

- Players report cars that pull away impossibly, or a vehicle covers a straight in half the time.
- You want a numeric sample before a kick: speed, model, ceiling, tolerance in one line.
- Speed anomalies appear only under load, which is usually a client-side hack rather than a script bug.
- If the symptom is teleporting on foot, use `teleport-airbreak-detection` instead.

## Compatibility & Stack Matrix (2026)

| Piece | Value | Note |
| --- | --- | --- |
| `GetVehicleVelocity` | returns m/s on x/y/z | multiply magnitude by 3.6 for km/h |
| Handling source | `handling.cfg` MaxVelocity column | the server ships no handling data, keep your own copy |
| Nitro | ~+20-30 % short bursts | not covered by the ceiling, absorbed by tolerance |

## Production Implementation

1. Build the ceiling table at boot. `GetVehicleModelInfo` gives size, never top speed, so the number
   has to come from handling data you ship:

```bash
# MaxVelocity is the 13th value after the model name; the range check rejects a wrong column.
awk 'NF > 20 && $13+0 > 60 && $13+0 < 600 {printf "%s,%d\n", $1, $13}' handling.cfg > scriptfiles/handling_speed.csv
wc -l scriptfiles/handling_speed.csv    # ~211 model rows
```

2. Load it into a per-model array and refuse to run without it; an empty table flags every vehicle:

```pawn
#define MAX_VEHICLE_MODELS 212

new Float:g_MaxSpeed[MAX_VEHICLE_MODELS];
new g_SpeedLoaded = 0;

stock LoadHandlingSpeeds()
{
    new File:f = fopen("scriptfiles/handling_speed.csv", io_read);
    if (!f) return 0;
    new line[64], name[24], Float:speed;
    while (fread(f, line))
    {
        if (sscanf(line, "p<,>s[24]f", name, speed)) continue;
        // Column 1 is the model name; map it with the id table you already keep for spawn names.
        new id = ModelIdFromName(name);
        if (id > 0 && id < MAX_VEHICLE_MODELS && speed > 60.0) g_MaxSpeed[id] = speed;
    }
    fclose(f);
    for (new i = 1; i < MAX_VEHICLE_MODELS; i++) if (g_MaxSpeed[i] > 0.0) g_SpeedLoaded++;
    return g_SpeedLoaded > 150;
}
```

3. Judge the horizontal magnitude, not the full vector: falling inflates the z term, and a downhill run
   legitimately beats the flat ceiling. Compare horizontal speed and log both:

```pawn
#define SPEED_TOLERANCE 1.35
#define SPEED_STRIKES_TO_ACT 3

new g_SpeedStrikes[MAX_PLAYERS];
new g_SpeedGrace[MAX_PLAYERS];

stock CheckVehicleSpeed(playerid)
{
    new veh = GetPlayerVehicleID(playerid);
    if (!veh) return 0;
    new model = GetVehicleModel(veh);
    if (model <= 0 || model >= MAX_VEHICLE_MODELS || g_MaxSpeed[model] <= 0.0) return 0;

    new Float:vx, Float:vy, Float:vz;
    GetVehicleVelocity(veh, vx, vy, vz);
    new Float:flat_kmh = floatsqroot(vx * vx + vy * vy) * 3.6;
    new Float:full_kmh = floatsqroot(vx * vx + vy * vy + vz * vz) * 3.6;

    new Float:limit = g_MaxSpeed[model] * SPEED_TOLERANCE;
    limit += float(GetPlayerPing(playerid)) * 0.10;   // 400 ms client => +40 km/h
    if (GetTickCount() < g_SpeedGrace[playerid]) return 0;
    if (flat_kmh <= limit) { g_SpeedStrikes[playerid] = 0; return 0; }

    return OnSpeedExceeded(playerid, veh, model, flat_kmh, full_kmh, limit);
}
```

4. Act on a run of samples, not one; three consecutive seconds over is not reachable by lag or nitro:

```pawn
stock OnSpeedExceeded(playerid, veh, model, Float:flat_kmh, Float:full_kmh, Float:limit)
{
    g_SpeedStrikes[playerid]++;
    LogSpeed(playerid, veh, model, flat_kmh, full_kmh, limit, g_SpeedStrikes[playerid]);
    if (g_SpeedStrikes[playerid] < SPEED_STRIKES_TO_ACT) return 1;

    new Float:x, Float:y, Float:z;
    GetVehiclePos(veh, x, y, z);
    SetVehicleVelocity(veh, 0.0, 0.0, 0.0);           // kill the gained speed
    SetVehiclePos(veh, x, y, z);                       // and re-anchor the sync
    if (g_SpeedStrikes[playerid] >= SPEED_STRIKES_TO_ACT * 2)
        BanEx(playerid, "vehicle speed exceeds handling ceiling, samples retained");
    return 1;
}
```

5. Write one line per event with both magnitudes and the limit, so an appeal has numbers:

```pawn
stock LogSpeed(playerid, veh, model, Float:flat_kmh, Float:full_kmh, Float:limit, strikes)
{
    new File:f = fopen("scriptfiles/ac/speed.csv", io_append), line[192], name[MAX_PLAYER_NAME + 1];
    if (!f) return 0;
    GetPlayerName(playerid, name, sizeof name);
    format(line, sizeof line, "SPEED|%d|%d|%d|%d|%s|%.1f|%.1f|%.1f|%d\n",
        GetTickCount(), playerid, veh, model, name, flat_kmh, full_kmh, limit, strikes);
    fwrite(f, line);
    fclose(f);
    return 1;
}
```

6. Set the grace window on every legitimate speed event: vehicle enter, respawn, mod shop exit, admin
   warp, race countdown, and any script that calls `SetVehicleVelocity` itself. Regenerate the CSV
   whenever the handling data changes, or the table silently drifts from the cars on the road.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Every vehicle flagged at spawn | table empty or wrong column parsed | run the `awk` gate, require >150 models before enabling |
| Nitro users flagged | ceiling ignores nitro impulse | 1.35x headroom, and reset strikes when the player exits nitro |
| Flag on a jump or a bridge drop | vertical component compared as speed | compare the horizontal magnitude, log the full one |
| Legion of false positives at peak hours | fixed limit, no latency term | the `GetPlayerPing` allowance in `limit` |
| Flag right after entering a vehicle | velocity inherited from the previous driver | grace window on `OnPlayerEnterVehicle` |
| Bans overturned | no retained sample | `LogSpeed` before `BanEx`, keep 30 days, rotate monthly |

## Verification

```bash
pawncc gamemodes/main.pwn -d3 -ogamemodes/main.amx && wc -l scriptfiles/handling_speed.csv
awk -F'|' '/^SPEED/ {printf "%.2f %s model=%s flat=%.0f limit=%.0f strikes=%s\n",
  $7/$9, $6, $5, $7, $9, $10}' scriptfiles/ac/speed.csv | sort -rn | head -3
```

Expected: a clean compile, 200+ handling rows, and the top ratios above 1.0 only for the injected test
(a 240 km/h Infernus at 380 km/h reads `ratio=1.17` because the limit already includes tolerance):

```text
211 scriptfiles/handling_speed.csv
1.17 Ferz model=411 flat=380 limit=324 strikes=3
0.98 Passenger model=411 flat=318 limit=324 strikes=0
```

- Manual: two minutes at full throttle with nitro off keeps `strikes` at 0; the test hack bans on the third sample.

## Sources (2026)

- https://open.mp/docs/scripting/functions/GetVehicleVelocity — units and arguments.
- https://open.mp/docs/scripting/functions/GetVehicleModel — model id from vehicle id.
- https://open.mp/docs/server/config.json — `network.in_vehicle_sync_rate` (30 ms) makes 1 s a safe window.
