---
name: teleport-airbreak-detection
description: Use when players teleport or fly across the map.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, anticheat, movement]
    category: samp
---

# Teleport and airbreak: measure distance per second, then revert

## When to Use

- A player crosses half the map between two samples, or hovers above the ground.
- Admins report speed hackers but you have no sample that survives an appeal.
- You want a revert plus a log, not a blind kick on the first bad sample.
- If only *damage* looks impossible, start with `fake-kill-bullet-crasher-shield`.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.4.x 2026 builds | `GetPlayerPos` is the authoritative server position |
| SA-MP server | 0.3.7-R5, 0.3.DL-R1 | same natives, client sample rate differs |
| OnPlayerUpdate | all | fires ~30x/s per player and varies: never put this loop inside it |
| pawncc | 3.10.11 or newer | `-d3`; expect 213 if a float is stored in an int |

## Production Implementation

1. Sample on a timer, not per update. One pass per second over the connected pool catches 40 m/s airbreak and costs nothing next to 30 callbacks per player per second:

```pawn
#define SAMPLE_MS 1000
#define MAX_ONFOOT_KMH 120.0
#define MAX_VEHICLE_KMH 400.0
#define SPEED_TOLERANCE 25.0

new Float:g_LastPos[MAX_PLAYERS][3];
new g_LastTick[MAX_PLAYERS], g_LastWorld[MAX_PLAYERS], g_LastInterior[MAX_PLAYERS];
new g_Strikes[MAX_PLAYERS], g_GraceUntil[MAX_PLAYERS];

public OnGameModeInit() return SetTimer("SampleMovement", SAMPLE_MS, true);

forward SampleMovement();
public SampleMovement()
{
    for (new playerid = 0, last = GetPlayerPoolSize(); playerid <= last; playerid++)
        if (IsPlayerConnected(playerid) && !IsPlayerNPC(playerid)) SamplePlayer(playerid);
    return 1;
}
```

2. Reject samples you cannot interpret before judging them. A stall, a respawn, a world or interior change, spectating and a warp your own code issued all look like teleports if you only compare coordinates:

```pawn
stock RecordSample(playerid, Float:x, Float:y, Float:z, now)
{
    g_LastPos[playerid][0] = x, g_LastPos[playerid][1] = y, g_LastPos[playerid][2] = z;
    g_LastTick[playerid] = now;
    g_LastWorld[playerid] = GetPlayerVirtualWorld(playerid);
    g_LastInterior[playerid] = GetPlayerInterior(playerid);
    return 1;
}

stock SamplePlayer(playerid)
{
    new now = GetTickCount(), dt = now - g_LastTick[playerid];
    new Float:x, Float:y, Float:z;
    GetPlayerPos(playerid, x, y, z);

    if (g_LastTick[playerid] == 0 || dt < 200 || dt > 3000        // first sample or stall
        || GetPlayerVirtualWorld(playerid) != g_LastWorld[playerid]
        || GetPlayerInterior(playerid) != g_LastInterior[playerid]
        || GetPlayerState(playerid) == PLAYER_STATE_SPECTATING
        || g_GraceUntil[playerid] > now)
        return RecordSample(playerid, x, y, z, now);

    new Float:dist = GetPlayerDistanceFromPoint(playerid, g_LastPos[playerid][0],
        g_LastPos[playerid][1], g_LastPos[playerid][2]);
    return JudgeSample(playerid, x, y, z, now, (dist / (float(dt) / 1000.0)) * 3.6);
}
```

3. Compare against a ceiling that grows with latency, because a 400 ms client legitimately moves further between two samples than a 40 ms client. Strike once, revert, and ban only on an unambiguous sample:

```pawn
stock JudgeSample(playerid, Float:x, Float:y, Float:z, now, Float:kmh)
{
    new Float:limit = IsPlayerInAnyVehicle(playerid) ? MAX_VEHICLE_KMH : MAX_ONFOOT_KMH;
    limit += float(GetPlayerPing(playerid)) * 0.5 + SPEED_TOLERANCE;

    if (kmh > limit)
    {
        g_Strikes[playerid]++;
        LogTeleport(playerid, g_LastPos[playerid], x, y, z, kmh, limit, g_Strikes[playerid]);
        if (IsPlayerInAnyVehicle(playerid))
            SetVehiclePos(GetPlayerVehicleID(playerid), g_LastPos[playerid][0],
                g_LastPos[playerid][1], g_LastPos[playerid][2]);
        else
            SetPlayerPos(playerid, g_LastPos[playerid][0], g_LastPos[playerid][1],
                g_LastPos[playerid][2]);
        if (kmh > limit * 2.0) BanEx(playerid, "teleport, sample retained");
        return 1;
    }
    g_Strikes[playerid] = 0;
    return RecordSample(playerid, x, y, z, now);
}
```

4. Write one line per event: both positions, the measured speed, the limit and the strike count. That is what an appeal gets judged on. The revert in step 3 already pulls the player back, in the vehicle when there is one, so gained ground never survives a sample:

```pawn
stock LogTeleport(playerid, const Float:from[3], Float:tx, Float:ty, Float:tz, Float:kmh, Float:limit, strikes)
{
    new File:f = fopen("ac/teleport.csv", io_append), line[256], name[MAX_PLAYER_NAME + 1];
    if (!f) return 0;
    GetPlayerName(playerid, name, sizeof name);
    format(line, sizeof line, "TELEPORT|%d|%d|%.1f|%.1f|%.1f|%.1f|%.1f|%.1f|%.1f|%.0f|%d|%s\n",
        GetTickCount(), playerid, from[0], from[1], from[2], tx, ty, tz, kmh, limit, strikes, name);
    fwrite(f, line);
    fclose(f);
    return 1;
}
```

5. Rotate the file after 30 days (`find scriptfiles/ac -name 'teleport.csv' -mtime +30 -delete`) and whitelist your own warps: every command that moves a player sets `g_GraceUntil[playerid] = GetTickCount() + 2000`. A ban without the log line above is not appealable.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Players rubber-band right after entering a vehicle | position jumps to the vehicle at enter time | refresh the sample in `OnPlayerEnterVehicle` and `OnPlayerExitVehicle` |
| Lagging mobile players flagged | fixed ceiling with no latency allowance | the ping term in `limit`; skip when `dt > 3000` |
| Everybody flagged after a server-side warp | grace flag never set | set `g_GraceUntil` in every teleport command |
| Interior doors flag players | interior change without a world change | keep interior in the guard shown above |
| Bans that cannot be defended | no retained sample | `LogTeleport` before `BanEx`, 30-day retention |

## Verification

```bash
./pawncc gamemodes/main.pwn -d3 -o gamemodes/main.amx
python3 - <<'PY'
rows = [l.strip().split("|") for l in open("scriptfiles/ac/teleport.csv") if l.startswith("TELEPORT")]
print("events", len(rows))
for tag, t, pid, fx, fy, fz, tx, ty, tz, kmh, limit, strikes, name in rows:
    d = ((float(tx)-float(fx))**2 + (float(ty)-float(fy))**2 + (float(tz)-float(fz))**2) ** 0.5
    print(f"t={t} pid={pid} kmh={float(kmh):.0f} limit={float(limit):.0f} strikes={strikes} dist={d:.0f}")
print("ban_candidates", sum(1 for r in rows if float(r[9]) > float(r[10]) * 2.0))
PY
```

Expected output for one airbreak attempt, two samples one second apart:

```text
events 2
t=1712000 pid=3 kmh=1440 limit=155 strikes=1 dist=400
t=1712500 pid=3 kmh=2880 limit=155 strikes=2 dist=800
ban_candidates 2
```

- Manual: a 24 h capture of normal traffic keeps `events` at 0 while players drive and fight; an admin warp that sets the grace flag writes no line.

## Sources (2026)

- https://open.mp/docs/scripting/callbacks/OnPlayerUpdate — fires about 30 times per second and varies; not a place for heavy work.
- https://open.mp/docs/scripting/functions/GetPlayerPos — server-side position is the reference for every sample.
- https://open.mp/docs/server/config.json — `network.on_foot_sync_rate` and `in_vehicle_sync_rate` set the client update rate.
