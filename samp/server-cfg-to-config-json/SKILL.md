---
name: server-cfg-to-config-json
description: Use when porting server.cfg to open.mp config.json.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, config]
    category: samp
---

# server.cfg to config.json

## When to Use

- An existing SA-MP 0.3.7 server moves to open.mp 1.6.x and the old `server.cfg` no longer describes the process.
- You need settings `server.cfg` cannot express: `artwork.*`, `npc.*` sync rates, `logging.timestamp_format`, env-var expansion.
- A config edit "did nothing" and you need to know which keys are live-changeable and which need a restart.
- You are containerising the server and want the port, password and hostname injected from the environment.

## Compatibility & Stack Matrix (2026)

| Component | Version / path | Notes |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 (`omp-server`) | has `--dump-config`, `--default-config`, `-c path=value` |
| Config file | `config.json` in the server root | `server.cfg` is still read through the LegacyConfig component |
| Generator | `./omp-server --default-config` | writes every key with its default value |
| Legacy converter | `./omp-server --dump-config` | writes `config.json`; delete an existing one first |
| Pawn entries | `pawn.main_scripts`, `pawn.side_scripts`, `pawn.legacy_plugins` | replace `gamemode0`, `filterscripts`, `plugins` |
| Read-only keys | `network.port`, `network.mtu`, `network.bind`, `max_players`, `artwork.*` | cannot be changed with `SendRconCommand` at runtime |
| Env expansion | `${VAR}`, `${VAR:-default}`, `$${VAR}` | resolved once at startup |

## Production Implementation

1. Back up the old file and produce a skeleton from the binary, not from memory:

```bash
cp server.cfg server.cfg.bak
rm -f config.json
./omp-server --default-config
```

2. Do not trust `--dump-config` to carry values. On 1.6.7.3218 a dump run against a hand-written
   `server.cfg` produced a full document filled with stock defaults (`"max_players": 50`, empty
   `rcon.password`). Diff before you believe it:

```bash
./omp-server --dump-config
grep -E '"name"|"max_players"|"rcon"' -A2 config.json
```

3. Translate the keys that matter. The left column is the legacy name, the right one the 2026 key:

| server.cfg | config.json |
| --- | --- |
| `hostname` | `name` |
| `rcon_password` | `rcon.password` |
| `maxplayers` | `max_players` |
| `maxnpc` | `max_bots` |
| `port` | `network.port` |
| `onfoot_rate` / `incar_rate` / `weapon_rate` | `network.on_foot_sync_rate` / `in_vehicle_sync_rate` / `aiming_sync_rate` |
| `stream_distance` / `stream_rate` | `network.stream_radius` / `network.stream_rate` |
| `announce` / `query` | `announce` / `enable_query` |
| `gamemode0 main 1` | `pawn.main_scripts: ["main 1"]` |
| `filterscripts admin race` | `pawn.side_scripts: ["admin", "race"]` |
| `plugins crashdetect.so` | `pawn.legacy_plugins: ["crashdetect"]` |

4. Write the file with only the keys you actually set. Unknown keys are ignored without a warning,
   so a typo is silent — every name below comes from the official table:

```json
{
  "name": "Your Server",
  "language": "English",
  "max_players": 100,
  "announce": true,
  "enable_query": true,
  "website": "https://example.com",
  "rcon": { "enable": true, "password": "${RCON_PASSWORD}" },
  "network": { "port": 7777, "mtu": 576, "stream_radius": 300.0, "stream_rate": 1000 },
  "pawn": {
    "main_scripts": ["main 1"],
    "side_scripts": ["admin"],
    "legacy_plugins": ["crashdetect"]
  },
  "artwork": { "enable": true, "models_path": "models" },
  "logging": { "file": "log.txt", "use_timestamp": true }
}
```

5. Validate the JSON before touching the live service — the server exits on a broken file and the
   error lands at the bottom of `log.txt`:

```bash
python3 -m json.tool config.json > /dev/null && echo "json ok"
```

6. Keep the RCON password out of git with environment expansion; export the variable in the unit
   file or compose file, then start:

```bash
export RCON_PASSWORD='change-me-per-host'
./omp-server --config-path config.json
```

7. `pawn.legacy_plugins` accepts both `crashdetect` and `crashdetect.so`; both resolve to
   `plugins/crashdetect.so`. Confirm the plugin really loaded instead of assuming it:

```bash
grep -nE 'Loading plugin|Legacy Network started|Loaded [0-9]+ component' log.txt
```

8. Keep one source of truth. While `server.cfg` stays in the directory the LegacyConfig component
   still reads it, so either edit both files or delete the old one after the first clean boot.

9. For one-off experiments use the CLI override instead of editing the file; it is the same
   `path=value` form the docs list:

```bash
./omp-server -c network.port=7778 -c name="Staging"
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `--dump-config` wrote stock values | the converter did not translate that `server.cfg` | re-apply `name`, `max_players`, `rcon.password`, `pawn.*` by hand and diff step 2 |
| Server uses the wrong port or hostname | both files exist and the legacy one wins | edit `config.json`, delete `server.cfg`, restart |
| Edited key has no effect | key is read-only at runtime, or the name has a typo | change the file and restart; copy names from the docs table |
| `rcon.password` is still `changeme` | shipped default was never replaced | set a strong value; some builds refuse to start with the default, others do not |
| Custom models return 404 | `artwork.enable` false or `models_path` points elsewhere | enable artwork and keep the files in `models/` |
| Hostname shows `${RCON_PASSWORD}` literally | variable unset and no fallback | use `${VAR:-fallback}` or export it in the unit |

## Verification

```bash
python3 -m json.tool config.json > /dev/null && echo "json ok"
grep -E '"main_scripts"|"legacy_plugins"' -A2 config.json
./omp-server & sleep 5; grep -E 'Loading plugin|Legacy Network started' log.txt; kill %1
```

Expected output:

```text
json ok
        "main_scripts": [
            "main 1"
        ],
[Info] Loading plugin: crashdetect
[Info]   CrashDetect plugin 4.21
[Info] Legacy Network started on port 7777
```

## Sources (2026)

- https://open.mp/docs/server/config.json
- https://open.mp/docs/server/server.cfg
- https://open.mp/docs/server/ControllingServer
