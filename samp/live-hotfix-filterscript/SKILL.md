---
name: live-hotfix-filterscript
description: Use when a one-file fix must ship without a restart.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, filterscript, ops, hotfix]
    category: samp
---

# Ship a hotfix as a filterscript, not a restart

## When to Use

- A command, a price or a message is wrong and `gmx` would drop 400 players.
- The fix is self-contained: one callback, one command, one table.
- You need a rollback path that takes seconds and does not touch the gamemode binary.
- You want a version line in the log that proves which fix is live.
- Not for editing running gamemode state; a filterscript cannot patch the gamemode's variables.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | console `loadfs` / `unloadfs` / `reloadfs` |
| RCON form | `/rcon loadfs <name>` | same commands, need `rcon.password` logged in |
| Path | `filterscripts/<name>.amx` | config `pawn.side_scripts` loads them at boot |
| Callback | `OnFilterScriptInit` / `OnFilterScriptExit` | only fire in the script being loaded or unloaded |
| Compiler | `pawncc` 3.10.10, `-d3` | same include set as the gamemode |
| State | lost on reload | globals, timers and arrays restart at init |
| Log proof | `Filterscript '<name>' loaded.` | measured on 1.6.7.3218 |

## Production Implementation

1. Write the fix as a normal filterscript with a tag and a version string, and print both on load.
   Without that line the log cannot tell you whether the fix is actually live:

```pawn
#include <open.mp>

#define HOTFIX_TAG      "hotfix_lottery"
#define HOTFIX_VERSION  "2026.11.26.1"

new bool:g_Ready;

public OnFilterScriptInit()
{
    g_Ready = true;
    print("[" HOTFIX_TAG "] loaded version=" HOTFIX_VERSION);
    return 1;
}

public OnFilterScriptExit()
{
    g_Ready = false;
    print("[" HOTFIX_TAG "] unloaded");
    return 1;
}
```

2. Own only your callbacks. Return `1` for commands you handled, `0` for everything else, or the fix
   swallows commands that belong to the gamemode:

```pawn
public OnPlayerCommandText(playerid, cmdtext[])
{
    if (!strcmp(cmdtext, "/hotfix", true))
    {
        new msg[96];
        format(msg, sizeof msg, "hotfix %s v%s ready=%d", HOTFIX_TAG, HOTFIX_VERSION, _:g_Ready);
        SendClientMessage(playerid, 0xFFFFFFFF, msg);
        return 1;      // ours
    }
    return 0;          // not ours: let the next script see it
}
```

3. Compile straight into the running server's filterscript folder, with the same flags as the
   gamemode:

```bash
pawncc -i"$HOME/samp-sdk/omp-stdlib" -d3 '-;+' '-(+' \
       -ofilterscripts/hotfix_lottery.amx hotfix_lottery.pwn
```

4. Load it from the console, or through RCON from in-game. The console needs no login; RCON does:

```bash
printf 'loadfs hotfix_lottery\nexit\n' | ./omp-server
# in game instead:
# /rcon loadfs hotfix_lottery
```

5. Read the log before telling anyone it worked. Two lines appear, one from the script and one from
   the server, and both are needed:

```bash
grep -a "hotfix_lottery" log.txt | tail -3
```

6. Roll back or update with `reloadfs`, never with a second `loadfs`. A reload unloads the old copy
   first, so the version line changes exactly once:

```bash
printf 'reloadfs hotfix_lottery\nexit\n' | ./omp-server
```

7. Fold the change into the gamemode, deploy that binary at the next natural restart, then remove
   the script from the runtime. Leaving it loaded after the merge means two scripts handling the same
   command:

```bash
printf 'unloadfs hotfix_lottery\nexit\n' | ./omp-server
```

8. Keep the hotfix source in the repository under `filterscripts/`, next to the commit that will
   absorb it. A hotfix that only exists on the box is lost at the next rebuild.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `loadfs` succeeds, nothing happens | no `OnFilterScriptInit`, or it returns `0` early | print a version line and return `1` |
| Command handled twice | `loadfs` called twice, two copies resident | `reloadfs` instead; check for two `loaded` lines |
| Fix vanishes after a restart | script not listed in `pawn.side_scripts` | add `filterscripts/hotfix_lottery` to the config |
| Counters reset at random | `reloadfs` restarts the script's globals | keep state in the database or accept the reset |
| New command never fires | another script handled it and returned `1` first | use a distinct command name for the hotfix |
| `loadfs` says unknown script | `.amx` not in `filterscripts/`, or name includes the extension | pass the bare name, compile into that folder |
| `rcon` command rejected | not logged in with `rcon.password` | use the console, or `/rcon login <password>` first |

## Verification

```bash
cd "$HOME/omp-runtime" && rm -f log.txt
(sleep 8; echo 'loadfs hotfix_lottery'; sleep 3; echo 'unloadfs hotfix_lottery'; sleep 3; echo exit) \
  | ./omp-server
grep -aE "hotfix_lottery|Filterscript" log.txt | tail -4
```

Expected output, captured from the run that produced this skill:

```text
[2026-11-26T07:51:51+0000] [Info] [hotfix_lottery] loaded version=2026.11.26.1
[2026-11-26T07:51:51+0000] [Info] Filterscript 'hotfix_lottery' loaded.
[2026-11-26T07:51:54+0000] [Info] [hotfix_lottery] unloaded
[2026-11-26T07:51:54+0000] [Info] Filterscript 'hotfix_lottery' unloaded.
```

Two `loaded` lines without an `unloaded` between them mean two resident copies - the case
`reloadfs` exists to prevent.

## Sources (2026)

- https://open.mp/docs/server/ControllingServer
- https://open.mp/docs/scripting/callbacks/OnFilterScriptInit
- https://open.mp/docs/scripting/functions/SendRconCommand
