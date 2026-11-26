---
name: legacy-to-openmp-migration
description: Use when a 0.3.7 gamemode moves to open.mp 1.6.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, migration, config]
    category: samp
---

# Move a 0.3.7 gamemode to open.mp without silent changes

open.mp runs SA-MP scripts, so a gamemode compiles on day one and then behaves
differently: a colour native is deprecated, a callback has a new tag, the pool
size function returns `-1`, and `server.cfg` is replaced by `config.json`. None of
that is a rewrite. It is a sequence of compiler-driven batches, each one verified
before the next, plus one config decision about 0.3.7 clients.

## When to Use

- A 0.3.7 gamemode must run on open.mp 1.6 and keep the same player behaviour.
- The compiler reports `warning 234` for deprecated natives you did not change.
- You are replacing `server.cfg` and plugins with `config.json` and components.
- Not for a fresh project: start on open.mp directly instead of porting.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | Linux x86 release, config-driven |
| Includes | `omp-stdlib` (`#include <open.mp>`) | replaces `<a_samp>`; `fixes.inc` is unnecessary |
| Compiler | pawncc 3.10.10 | `-;+ -(` required for the community compiler |
| Config | `config.json` | `./omp-server --dump-config` converts an existing `server.cfg` |
| Clients | 0.3.7 and open.mp launcher | `network.allow_037_clients` (default `true`) |
| Plugins | `pawn.legacy_plugins`, `components/` | Pawn.CMD and Pawn.RakNet need `-omp` builds |

## Production Implementation

1. Convert the config first, so behaviour changes are visible in one file instead
   of being guessed from the old `server.cfg`.

```bash
./omp-server --dump-config      # writes config.json from server.cfg
grep -n 'allow_037_clients\|main_scripts\|legacy_plugins' config.json
```

2. Switch the include. `fixes.inc` and `YSF` must go: open.mp already declares
   those natives and callbacks, and keeping them redefines what the server fixes.

```pawn
#include <open.mp>          // was: #include <a_samp>

public OnPlayerDeath(playerid, killerid, WEAPON:reason)
{
    return 1;
}
```

3. Compile with warnings enabled and migrate by compiler message, not by
   grep. Renamed natives are deprecated aliases, so the build points at each one.

```bash
pawncc -i$HOME/samp-sdk/omp-stdlib -d3 '-;+' '-(' gamemodes/rp.pwn -orp.amx 2>&1 \
  | grep 'warning 234'
```

| Deprecated symbol | Replacement | Since |
| --- | --- | --- |
| `TextDrawColor` | `TextDrawColour` | open.mp 1.1.0.2612 |
| `TextDrawBoxColor` | `TextDrawBoxColour` | 1.1.x |
| `TextDrawBackgroundColor` | `TextDrawBackgroundColour` | 1.1.x |
| `PlayerTextDrawColor` | `PlayerTextDrawColour` | 1.1.x |
| `ChangeVehicleColor` | `ChangeVehicleColours` | 1.1.x |
| `GetVehicleColor` | `GetVehicleColours` | 1.1.x |
| `GangZoneGetColorForPlayer` | `GangZoneGetColourForPlayer` | 1.1.x |
| `GetPlayerPoolSize` | `MAX_PLAYERS` or `foreach` | 1.x |

4. Do not silence the warnings globally. `MIXED_SPELLINGS` and `SAMP_COMPAT`
   exist to keep old code compiling during the port; defining them permanently
   means nobody notices the next renamed native.

```pawn
// temporary only, remove before the migration is declared done
// #define SAMP_COMPAT
```

5. Replace pool-size loops. open.mp changed `GetPlayerPoolSize()` to return `-1`
   with no players and deprecated it, so a `for (i = 0; i <= GetPlayerPoolSize(); i++)`
   now skips the loop when the server is empty and warns on every build.

```pawn
foreach (new i : Player)          // YSI 5
{
    SendClientMessage(i, 0xFFFFFFFF, "restarting");
}
```

6. Move plugins that changed type. Pawn.CMD and Pawn.RakNet are components on
   open.mp; sscanf and streamer stay plugins, but the builds are different.

```json
{
  "pawn": {
    "main_scripts": ["rp 1"],
    "legacy_plugins": ["sscanf", "streamer"]
  },
  "network": { "allow_037_clients": true, "use_omp_encryption": false }
}
```

7. Keep 0.3.7 clients allowed while both generations exist, then flip one key
   after the launcher rollout. Do not enable `use_omp_encryption` before that
   flip: old clients cannot negotiate it.

```json
{ "network": { "allow_037_clients": false, "use_omp_encryption": true } }
```

8. Diff the flow, not the whole log. Run the same scripted session (connect,
   spawn, die, use a command, disconnect) on both targets and compare the lines
   your gamemode prints.

```bash
diff <(grep '^\[rp\]' old/log.txt | head -100) <(grep '^\[rp\]' new/log.txt | head -100)
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Hundreds of `warning 234` on first build | all renamed natives at once | migrate batch by batch, recompile after each |
| Server refuses to start, gamemode not found | `pawn.main_scripts` still names the old script | set `["rp 1"]` to match `gamemodes/rp.amx` |
| `Function not found` / runtime error 19 | plugin listed in `legacy_plugins` but missing from `plugins/` | ship the `-omp` build or move it to `components/` |
| Callback never fires after porting | `fixes.inc` or YSF still included and redefining it | delete both includes and rebuild |
| Empty-server loops do nothing | `GetPlayerPoolSize()` returns `-1` | `foreach` or `MAX_PLAYERS` |
| Old clients cannot connect after enabling encryption | `use_omp_encryption` before dropping 0.3.7 | keep `allow_037_clients: true` until the flip |

## Verification

```bash
./omp-server --dump-config && grep -c '"' config.json
pawncc -i$HOME/samp-sdk/omp-stdlib -d3 '-;+' '-(' gamemodes/rp.pwn -orp.amx 2>&1 \
  | grep -cE '(error|warning) [0-9]+:'
grep -rn 'GetPlayerPoolSize\|fixes.inc\|#include <a_samp>' gamemodes/ || echo "clean"
```

- The compiler count is `0`: no errors and no warnings on the ported gamemode.
- `clean` means no removed include and no deprecated pool-size call remains.
- A 0.3.7 client and an open.mp client both connect, spawn and die with the same
  `[rp]` lines in the log.

## Sources (2026)

- https://open.mp/docs/server/config.json
- https://open.mp/docs/scripting/functions/GetPlayerPoolSize
- https://open.mp/docs/scripting/functions/TextDrawColour
