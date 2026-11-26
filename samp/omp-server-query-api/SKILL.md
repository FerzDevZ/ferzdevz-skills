---
name: omp-server-query-api
description: Use when a site or bot needs live open.mp server data.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, api, query]
    category: samp
---

# Serve server information over the SA-MP query protocol

The query "API" of an open.mp server is not HTTP and has no JSON endpoint: it is the SA-MP UDP
query protocol on the game port, plus the rule names your script publishes. A website showing
status is a client of that protocol.

## When to Use

- A UCP, launcher, Discord bot or status page needs the live hostname, player count or mode.
- The server is listed but shows "offline" or 0 players while people are playing.
- You want gamemode state (season, map, version) visible in the browser without RCON.
- Someone proposes scraping the log or opening a second port for status: neither is needed.

## Compatibility & Stack Matrix (2026)

| Item | Value | Notes |
| --- | --- | --- |
| Transport | UDP on `network.port` | game traffic, query and RCON share one socket |
| Request header | `SAMP` + 4 IP octets + port low + port high + opcode | 11 bytes, no length field |
| `i` opcode | server info | password flag, players, max players, hostname, gamemode, language |
| `r` opcode | rules | count, then name/value pairs, one byte length each |
| `c` / `d` opcode | player list / detailed list | `d` adds player id and ping |
| `p` opcode | ping echo | four bytes round-tripped |
| `x` opcode | RCON | plaintext password in the packet |
| Query toggle | `enable_query` in `config.json` | default true; false hides info from the browser |
| Rule natives | `AddServerRule`, `SetServerRule`, `RemoveServerRule`, `IsValidServerRule` | open.mp 1.1.0.2612 and newer |
| Debugging | `logging.log_queries` | logs every incoming query |

Rule values are limited to one byte of length each: keep them short, and never put a secret
there, because `r` is answered to anyone who can reach the port.

## Production Implementation

1. Set identity once in `config.json` and leave querying on. `game.mode` is the browser column,
   and `SetGameModeText` overrides it at runtime:

```json
{
  "name": "Your Server 2026",
  "language": "English",
  "enable_query": true,
  "network": { "port": 7777, "bind": "" },
  "game": { "mode": "Freeroam", "map": "San Andreas" },
  "logging": { "log_queries": false }
}
```

2. Publish static rules in `OnGameModeInit`. They are read on every `r` request, so write them
   once instead of rebuilding them from state:

```pawn
public OnGameModeInit()
{
    SetGameModeText("Freeroam 2026");
    AddServerRule("mode", "Freeroam");
    AddServerRule("version", "1.4.0");
    AddServerRule("discord", "discord.gg/example");
    printf("[query] version rule=%d", IsValidServerRule("version"));
    return 1;
}
```

3. Change a rule only when its value changes - a season flip, a map rotation, maintenance.
   `SetServerRule` replaces in place, `RemoveServerRule` makes the browser forget the entry:

```pawn
stock SetSeason(const name[])
{
    SetServerRule("season", name);
    printf("[query] season=%s", name);
    return 1;
}

stock ClearEvent()
{
    RemoveServerRule("event");
    return 1;
}
```

4. Never derive the player count from a rule: the count in the `i` response is produced by the
   server, and a hand-maintained rule drifts the moment someone times out. Do not write rules in
   a timer either - that is a lock every tick for a value nobody polls that fast.

5. Keep secrets out: RCON password, database host, admin counts, player IPs and staff names do
   not belong in rules, because `r` is unauthenticated. Turn RCON off (`rcon.enable` false).

6. Read it from outside with the protocol itself. This client asks for `i`, then `r`, and prints
   what the browser sees:

```python
import socket, struct, sys

host, port = sys.argv[1], int(sys.argv[2])
hdr = b"SAMP" + bytes(int(o) for o in host.split(".")) + struct.pack("<H", port)

def ask(opcode):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2.0)
    s.sendto(hdr + opcode, (host, port))
    return s.recv(4096)

d = ask(b"i")
o = 16
n = struct.unpack_from("<I", d, o)[0]; o += 4
name = d[o:o + n].decode("latin-1"); o += n
n = struct.unpack_from("<I", d, o)[0]; o += 4
mode = d[o:o + n].decode("latin-1")
print("password=%d players=%d/%d hostname=%s mode=%s"
      % (d[11], struct.unpack_from("<H", d, 12)[0],
         struct.unpack_from("<H", d, 14)[0], name, mode))

d = ask(b"r")
count = struct.unpack_from("<H", d, 11)[0]
o, rules = 13, {}
for _ in range(count):
    ln = d[o]; o += 1
    key = d[o:o + ln].decode("latin-1"); o += ln
    ln = d[o]; o += 1
    rules[key] = d[o:o + ln].decode("latin-1"); o += ln
print("rules=%d version=%s" % (count, rules.get("version", "-")))
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Listed, but "offline" or 0 players | `enable_query` false, or UDP blocked | set true, open `network.port`/UDP |
| Query answers, browser still empty | `announce` false or masterlist unreachable | enable announce, check egress |
| Rules missing | published after init, or removed | publish in `OnGameModeInit`, check `IsValidServerRule` |
| Rule value truncated | value longer than 255 bytes | shorten it, move detail to a website |
| Password leaks in a status page | `r` response copied verbatim | filter keys server-side or omit secrets |
| Player count wrong | scripted count rule instead of packet data | read the `i` response, drop the rule |
| RCON brute-forced | RCON enabled on a public UDP port | `rcon.enable` false, or firewall the port |

## Verification

```bash
python3 query.py 127.0.0.1 7777
grep -rhoE 'AddServerRule\("[a-z_]+"' gamemodes/ | sort -u
```

```text
password=0 players=12/100 hostname=Your Server 2026 mode=Freeroam
rules=6 version=1.4.0
AddServerRule("discord"
AddServerRule("mode"
AddServerRule("version"
```

A timeout instead of the first line means no UDP answer: check `enable_query`, the port, and
that the host is up - a closed port and a disabled query both look "offline" in the browser,
and only the script separates them by timing out versus answering.

## Sources (2026)

- https://open.mp/docs/tutorials/QueryMechanism
- https://open.mp/docs/scripting/functions/AddServerRule
- https://open.mp/docs/server/config.json
