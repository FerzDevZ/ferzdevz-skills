---
name: omp-legacy-plugin-bridge
description: Use when a legacy plugin must sit beside open.mp components.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, plugins, components, natives]
    category: samp
---

# Bridge a legacy plugin into open.mp without shadowing a native

## When to Use

- A dependency still ships only as a 32-bit SA-MP plugin and has no open.mp component build.
- The server starts, but the gamemode dies with `Run time error 19: "File or function not found"`.
- A plugin and a component both claim the same native, and calls land in the wrong implementation.
- You are deciding between `components/` and `plugins/` for one specific binary.
- Not for migrating Pawn source off old includes; that is `legacy-to-openmp-migration`.

## Compatibility & Stack Matrix (2026)

| Location | Loaded by | Config key | Behaviour |
| --- | --- | --- | --- |
| `components/*.so` / `*.dll` | open.mp core, before any AMX | none | auto-loaded, cannot be turned off per script |
| `plugins/*.so` | the Pawn loader, in list order | `pawn.legacy_plugins` | file name only, path resolved inside `plugins/` |
| `server.cfg` `plugins` line | legacy config reader | `plugins` | still read, but keep one source of truth |
| Pawn.CMD, Pawn.RakNet, sscanf, sampvoice, discord-connector | open.mp builds exist | `pawn.legacy_plugins` | put the `-omp` builds in `components/`, not `plugins/` |
| YSF | not needed | none | its natives are declared by open.mp core |
| FCNPC | replaced | none | use the built-in NPC component |
| `profiler`, `rustext`, `keylistener` | legacy only | `pawn.legacy_plugins` | check the specific release for an open.mp build |

## Production Implementation

1. Inventory providers before touching folders. One native, one owner:

```bash
# every native the gamemode includes can reach
grep -Rh -E "^[[:space:]]*native[[:space:]]" include/ gamemodes/ | awk '{print $2}' | sort -u > natives.txt
# every native the legacy plugin's own include declares
grep -h -E "^[[:space:]]*native[[:space:]]" plugins/profiler.inc | awk '{print $2}' | sort -u > provided.txt
comm -12 natives.txt provided.txt        # anything printed here exists twice
```

2. Put the binary where its build belongs. A component build goes to `components/` and needs no entry;
   a classic plugin goes to `plugins/` and must be named in `config.json`:

```json
{
  "pawn": {
    "main_scripts": ["gamemode 1"],
    "legacy_plugins": ["profiler.so"]
  }
}
```

3. Delete the duplicate, never "disable" it. Open.mp registers natives once; a second provider of
   `SetPlayerPos` or `GetPlayerPoolSize` is a coin flip at call time and invisible in the log.

4. Prove registration at boot instead of discovering it at the first call. `funcidx` returns `-1` for a
   name the AMX never resolved, natives included:

```pawn
stock bool:HasNative(const name[])
{
    return funcidx(name) != -1;
}

public OnGameModeInit()
{
    if (!HasNative("Profiler_Start"))
    {
        print("[bridge] profiler plugin missing - profiling disabled");
    }
    if (!HasNative("Streamer_UpdateEx"))
    {
        print("[bridge] streamer missing - refusing to start the map");
        SendRconCommand("exit");
        return 0;
    }
    return 1;
}
```

5. Do not call a plugin from another plugin's init. Components load first, legacy plugins second, and the
   order inside each group is not a contract you control. Defer cross-plugin work by one tick:

```pawn
public OnGameModeInit()
{
    SetTimer("BridgeAfterInit", 100, false);   // everything is registered by now
    return 1;
}

forward BridgeAfterInit();
public BridgeAfterInit()
{
    if (HasNative("Profiler_Start")) Profiler_Start();
    return 1;
}
```

6. Keep the plugin's own config file. Several legacy plugins parse `server.cfg` with their own reader and
   never look at `config.json`, so their keys belong in `server.cfg` even on an open.mp server.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Run time error 19: "File or function not found"` | the binary is not in `plugins/`, or not named in `pawn.legacy_plugins` | list the exact file name, restart, confirm the loader reports it |
| `Failed to load plugin: invalid ELF header` / `not a valid Win32 application` | 64-bit or wrong-OS build | ship the 32-bit Linux `.so` for Linux, the `.dll` for Windows |
| Natives resolve, behaviour is subtly wrong, no error | plugin and component both registered the same native | keep exactly one provider, delete the other binary |
| Plugin settings silently ignored | the plugin reads `server.cfg`, the server runs `config.json` | keep the plugin's keys in `server.cfg` |
| Works after a manual restart, fails on boot | plugin init ran before components finished registering | defer the first call to a 100 ms timer |
| Two filterscripts disagree about a native's behaviour | one script loaded an older copy of the include | pin one include version in `dependencies` |

## Verification

```bash
./omp-server > boot.log 2>&1 &
sleep 5
grep -Ei "failed to load|already registered|could not find" boot.log ; echo "conflicts_exit=$?"
grep -c "Loaded component" boot.log
```

Expected output on a clean bridge: no `failed to load`, no `already registered`, and a component count
equal to the number of `.so` files in `components/`:

```text
conflicts_exit=1
6
```

Then confirm the runtime probe agrees with the boot log by connecting and grepping the callback output:

```bash
grep -E "\[bridge\]" server.log | tail -5
```

## Sources (2026)

- https://open.mp/docs/server/Installation
- https://open.mp/docs/server/config.json
- https://github.com/inject3r/FakeBots
