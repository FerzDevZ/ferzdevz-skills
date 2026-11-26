---
name: ysi-y-hooks-modularization
description: Use when one callback must run from several modules.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi]
    category: samp
---

# Splitting callbacks with YSI y_hooks

## When to Use
- One `main.pwn` carries a 900-line `OnPlayerConnect` and every feature edits the same function.
- Two subsystems need the same callback and the last edit deleted the other team's code.
- You want a feature to be deletable by removing one `#include` line.

## Compatibility & Stack Matrix (2026)
| Component | Version | Notes |
| --- | --- | --- |
| YSI | 5.x (`YSI_Coding/y_hooks.inc`) | hooks are resolved at AMX load; no plugin binary |
| open.mp | 1.x | identical behaviour; callbacks come from the component set |
| SA-MP | 0.3.7-R5 | identical behaviour |
| pawncc | 3.10.10+ | `-;+ -(+ -d3`; debug info is what lets crashdetect cross a hook |
| Include path | `-i./includes` | `<YSI_Coding\y_hooks>` must resolve to `includes/YSI_Coding/y_hooks.inc` |

YSI is not shipped with the server: install the 5.x includes first, then compile a one-line file that includes `<YSI_Coding\y_hooks>` and confirm it resolves before moving any code. The backslash in the include name works on Linux as well as Windows.

## Production Implementation
1. Install YSI 5.x so `includes/YSI_Coding/y_hooks.inc` exists; keep `-i./includes` in every build.
2. Keep one entry script that includes core, then `y_hooks`, then the modules in dependency order.
3. In each module, guard the include, then declare `hook` blocks — never `public OnPlayerConnect`.
4. Move the module's state into `static` variables in the same file; the hook is now its only entry point.
5. Treat include order as part of the contract and write the reason in a comment next to the includes.

```pawn
// gamemodes/main.pwn
#include <open.mp>
#include <YSI_Coding\y_hooks>

// Order matters: accounts must reset the slot before vehicles read it.
#include "modules/accounts.pwn"
#include "modules/vehicles.pwn"
#include "modules/chat.pwn"

main() {}
```

```pawn
// gamemodes/modules/accounts.pwn
#if !defined _INC_y_hooks
    #include <YSI_Coding\y_hooks>
#endif

static bool:gAccountReady[MAX_PLAYERS];

hook OnPlayerConnect(playerid)
{
    gAccountReady[playerid] = false;
    LoadAccount(playerid);
    return 1;                       // 1 keeps the chain going to the next hook
}

hook OnPlayerDisconnect(playerid, reason)
{
    UnloadAccount(playerid);
    return 1;
}
```

A hook returning `0` or `1` does **not** stop the chain — the chain runs every hook, then the final value wins. Only `~0` / `~1` halt it immediately:

```pawn
hook OnPlayerConnect(playerid)
{
    new name[MAX_PLAYER_NAME];
    GetPlayerName(playerid, name, sizeof name);
    if (IsBanned(name))
        return ~1;                  // halt the chain now, report the callback as handled
    return 1;
}
```

Function hooks wrap natives or your own functions and chain explicitly with `continue(...)`:

```pawn
hook function SendClientMessage(playerid, colour, const message[])
{
    if (isnull(message)) return 1;  // drop empty sends for every caller, skip the original
    return continue(playerid, colour, message);
}
```

## Failure Modes & Fixes
| Symptom | Cause | Fix |
| --- | --- | --- |
| a module's hook never runs | the `.pwn` was never `#include`d into the AMX | include it from `main.pwn`; hooks do not cross AMX boundaries |
| the callback runs twice per event | a leftover `public OnPlayerConnect` in the module | delete the public; the hook replaces it |
| one module stops the others | `return ~0` / `~1` in an unrelated hook | grep `~0` and `~1`; use them only for real vetoes |
| `error 021: symbol already defined` | two modules define the same helper | make module-local functions `static` |
| behaviour changes after a merge | include order changed | order is declaration order; document it |
| `fatal error 100: cannot read from file` | include path or YSI not installed | fix `-i`, verify `includes/YSI_Coding/y_hooks.inc` exists |
| works in the gamemode, not in a filterscript | separate scripts have separate chains | put the module in the same AMX, or hook in both |

## Verification
```bash
grep -rn "public On" gamemodes/ | grep -v "gamemodes/main.pwn"
```
Expected: no output — no plain callback publics outside the entry script.

```bash
grep -rc "^hook OnPlayerConnect" gamemodes/modules/*.pwn
```
Expected: one line per module, each count `1` (or `0` for modules that do not hook connect).

```bash
pawncc -i./includes -d3 -;+ -(+ -ogamemodes/main.amx gamemodes/main.pwn 2>&1 | tail -1
```
Expected: `0 Errors`. With `printf("[hooks] connect %d", playerid);` in the accounts hook, one connect writes exactly one `[hooks] connect 7` line — two lines mean a duplicate public survived.

## Sources (2026)
- [y_hooks quick start](https://raw.githubusercontent.com/pawn-lang/YSI-Includes/5.x/YSI_Coding/y_hooks/quick-start.md) — original, callback and function hook forms, `continue(...)`.
- [y_hooks features](https://raw.githubusercontent.com/pawn-lang/YSI-Includes/5.x/YSI_Coding/y_hooks/features.md) — chain order, `return 0/1` semantics, `~0`/`~1`, `DEFINE_HOOK_RETURN__`.
- [YSI-Includes 5.x](https://github.com/pawn-lang/YSI-Includes) — library layout and the `YSI_Coding\y_hooks` include path.
