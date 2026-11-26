---
name: tablist-headers-formatting
description: Use when the TAB list header or name rows look wrong.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ui, scoreboard]
    category: samp
---

# TAB list: the header is config, the rows are names and scores

There is no Pawn native for the TAB list header. The header text the client renders is
the server `name` it received from the query/connection data, i.e. the `name` key in
`config.json`. Everything else in that panel is per-player: display name (max 24 chars),
score, ping and name colour.

## When to Use

- The header still says the default `open.mp server`, or branding must change.
- Row names are cut off, ragged, or the tag pushes the nick over the limit.
- `SetPlayerName` returns `-1` and the name silently does not change.
- Not for a custom overlay: if the panel must show live counters, that is a TextDraw
  overlay (`textdraw-scrollbar-list-grid`), not the TAB list.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | `name` in `config.json` is the header source |
| Row name | `SetPlayerName` | 1-24 chars, charset `0-9 a-z A-Z [] () $ @ . _ =` |
| Row number | `SetPlayerScore` | integer column; the level/score goes here |
| Row colour | `SetPlayerColor` | colours the name in the list |
| Ping | client-derived | never writable from the script |
| Legacy | SA-MP 0.3.7 | same limits, `hostname` in `server.cfg` |

## Production Implementation

1. Set the header once, in config, then confirm what the network layer actually sends:

```json
{
  "name": "Your Server | Freeroam | 2026",
  "language": "English",
  "max_players": 100
}
```

Keep the header short and static — a live player count in it is impossible, because the
value is announced at connect and the browser caches the query response.

2. Fit the row to 24 characters. Build `tag + nick` with an explicit budget and truncate
the nick, never the tag — a half tag looks like a broken name:

```pawn
stock bool:ApplyRow(playerid, const tag[], const nick[])
{
    new budget = 24 - strlen(tag);
    if (budget < 3) return false;          // tag alone eats the field

    new cut[24], row[24];
    strmid(cut, nick, 0, budget, sizeof cut);
    format(row, sizeof row, "%s%s", tag, cut);

    return SetPlayerName(playerid, row) == 1;
}
```

`SetPlayerName` returns `0` when the name is taken and `-1` for an illegal length or
character, so the boolean result is the only check you need.

3. Keep the original nick. Once the row is rewritten the real name is gone, and
`/untag` or an admin action cannot recover it:

```pawn
new g_RealNick[MAX_PLAYERS][24];
new g_TagApplied[MAX_PLAYERS];

public OnPlayerConnect(playerid)
{
    GetPlayerName(playerid, g_RealNick[playerid], 24);
    g_TagApplied[playerid] = 0;
    return 1;
}

stock bool:SetTag(playerid, const tag[])
{
    if (!ApplyRow(playerid, tag, g_RealNick[playerid])) return false;
    g_TagApplied[playerid] = 1;
    SetPlayerScore(playerid, g_Level[playerid]);   // keep the score column owned
    SetPlayerColor(playerid, 0x33AA33FF);
    return true;
}

stock RestoreNick(playerid)
{
    if (!g_TagApplied[playerid]) return 0;
    SetPlayerName(playerid, g_RealNick[playerid]);
    g_TagApplied[playerid] = 0;
    return 1;
}
```

4. Refresh on events, not on a timer. Name and score change on rank-up, team change and
   admin action; a 1 s loop that rewrites names is pure churn and flickers the list:

```pawn
stock OnRankUp(playerid, newlevel)
{
    g_Level[playerid] = newlevel;
    SetPlayerScore(playerid, newlevel);
    return 1;
}
```

5. Do not let two systems write the score column: if a stats panel already owns
   `SetPlayerScore`, put the level there instead of money.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Header unchanged after editing config | value read at boot | restart the server, re-query |
| Header truncated in the browser | `name` too long for the list column | shorten it; check the query reply |
| `SetPlayerName` returns `-1` | row longer than 24 chars or illegal char | use the budget + `strmid` helper |
| Nick lost after tagging | original never stored | cache it in `OnPlayerConnect` |
| Score flickers between two values | two writers of the score column | single owner, level in score |
| Names look ragged | tags of different length | pad the tag to fixed width |
| Colour does not match the row | `SetPlayerColor` never applied, or reset on spawn | set it after spawn/team change |

## Verification

Ask the server what it actually announces, using the query protocol the client uses:

```python
import socket, struct
HOST, PORT = "127.0.0.1", 7777
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(3)
s.sendto(b"SAMP" + bytes(map(int, HOST.split("."))) + struct.pack("<H", PORT) + b"i",
         (HOST, PORT))
d = s.recv(2048)
o = 11
password = d[o]
players, maxplayers = struct.unpack_from("<HH", d, o + 1)
o += 5
def read_str():
    global o
    n = struct.unpack_from("<I", d, o)[0]; o += 4
    v = d[o:o + n].decode("cp1252"); o += n
    return v
hostname = read_str()
print(f"header={hostname!r} len={len(hostname)} players={players}/{maxplayers}")
print("gamemode=", read_str(), "language=", read_str())
```

Expected: `header='Your Server | Freeroam | 2026' len=29 players=3/100` and the gamemode
and language you configured. If the header differs, the running process did not reload
`config.json`.

Then check the rows in game: press TAB, every name must be `<= 24` characters with the
tag intact, and the score column must equal the level.

## Sources (2026)

- https://open.mp/docs/server/config.json
- https://open.mp/docs/scripting/functions/SetPlayerName
- https://open.mp/docs/scripting/functions/SetPlayerScore
