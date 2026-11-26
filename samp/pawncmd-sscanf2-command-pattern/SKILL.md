---
name: pawncmd-sscanf2-command-pattern
description: Use when commands need typed, validated arguments.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, commands, sscanf]
    category: samp
---

# Typed commands with Pawn.CMD and sscanf2

## When to Use
- A `strcmp` ladder inside `OnPlayerCommandText` is now the largest function in the gamemode.
- Command arguments need types and domains: a target that must be an online player, an amount that must be positive.
- You want aliases, per-command permission flags, and a single answer for "unknown command" instead of one per command.

## Compatibility & Stack Matrix (2026)
| Component | Version | What it provides |
| --- | --- | --- |
| Pawn.CMD | 3.4.0-omp | `cmd:` macro (`CMD:` and `COMMAND:` are aliases of it), `alias:`, `flags:`, `OnPlayerCommandReceived` / `OnPlayerCommandPerformed` |
| sscanf2 | 2.15.1 | `sscanf(params, "ri", id, amount)`, string lengths, escaped strings, name-to-id lookup |
| pawncc | 3.10.10+ | `-;+ -(+ -d3` so both targets accept the same source |
| open.mp | 1.x | `pawncmd` in `pawn.legacy_plugins`; `sscanf` binary in `components/` |
| SA-MP | 0.3.7-R5 | `plugins pawncmd.so sscanf.so` in `server.cfg` |

Both libraries are external binaries plus an include. Install `pawncmd.so`/`pawncmd.dll` and `sscanf.so`/`sscanf.dll`, then confirm the include actually resolves from the `-i` path before blaming the code.

## Production Implementation
1. Install the binaries, start the server once, and confirm both `Loading plugin: pawncmd.so` and the sscanf version line appear in the log.
2. Include both headers once in the entry script, before any file that declares a command.
3. Declare permission bits as a single-bit enum; store a per-player mask.
4. Write the command body as extraction, then domain validation, then effect, then `return 1`.
5. Attach `flags:` before the command and `alias:` after it (both are macro statements, no trailing semicolon).
6. Answer unknown commands and refusals centrally in the two Pawn.CMD callbacks.

```pawn
#include <Pawn.CMD>
#include <sscanf2>

enum (<<= 1)
{
    CMD_ADMIN = 1,
    CMD_MODER
};

new gMask[MAX_PLAYERS];

flags:setmoney(CMD_ADMIN)
CMD:setmoney(playerid, params[])
{
    new targetid, amount;

    if (sscanf(params, "ri", targetid, amount))
        return SendClientMessage(playerid, 0xFF4444FF, "Usage: /setmoney <player> <amount>");

    if (targetid == INVALID_PLAYER_ID)
        return SendClientMessage(playerid, 0xFF4444FF, "No such player online.");

    if (amount < 0 || amount > 1000000)
        return SendClientMessage(playerid, 0xFF4444FF, "Amount must be 0..1000000.");

    ResetPlayerMoney(targetid);
    GivePlayerMoney(targetid, amount);
    return 1;
}
alias:setmoney("setcash", "givemoney")
```

```pawn
public OnPlayerCommandReceived(playerid, cmd[], params[], flags)
{
    if ((flags & CMD_ADMIN) && !(gMask[playerid] & CMD_ADMIN))
    {
        SendClientMessage(playerid, 0xFF4444FF, "Insufficient rights.");
        return 0;                      // 0 aborts the command before it runs
    }
    return 1;
}

public OnPlayerCommandPerformed(playerid, cmd[], params[], result, flags)
{
    if (result == -1)                  // -1 means no command matched
    {
        SendClientMessage(playerid, 0xFF4444FF, "Unknown command. Try /help.");
        return 0;
    }
    return 1;
}
```

Specifiers are bare letters, not `printf` conversions. `"ri"` is correct; `"%d %s"` is not:

| Specifier | Accepts | Trap |
| --- | --- | --- |
| `i`, `d` | signed integer | no range; validate the bound yourself |
| `f` | float | destination must be `Float:x` |
| `s[64]` | string up to 64 cells | without `[n]` you get a buffer-overflow warning |
| `s[128]` last | the rest of the line | only safe as the final specifier |
| `r` | player name or id | returns `INVALID_PLAYER_ID`, never `0` |
| `u` | player or NPC | includes bots |
| `q` | NPC name or id | it is **not** a quoted string |
| `{i}` | quiet: checked, not stored | still counts toward the return value |

A leading `%` still parses but raises `sscanf warning: sscanf specifiers do not require '%' before them`, and there is no quoted-string specifier — take free text with a final `s[128]`.

## Failure Modes & Fixes
| Symptom | Cause | Fix |
| --- | --- | --- |
| `SERVER: Unknown command` for a command that compiles | plugin binary missing, so `pc_cmd_*` publics were never registered | check the plugin load line; match the 32/64-bit and open.mp build |
| every command prints the usage line | `%`-prefixed tokens or a specifier/parameter count mismatch | strip `%`, count specifiers against arguments |
| `sscanf warning: String buffer overflow` | `s` without a length | declare `s[64]` matching the destination size |
| admin command usable by everyone | `flags:` omitted, or `OnPlayerCommandReceived` not defined | define the callback, return `0` on refusal |
| command hits the wrong player | parsed id trusted | compare with `INVALID_PLAYER_ID` and `IsPlayerConnected` |
| duplicate-command warning at boot | the same name declared in two files | one definition, `alias:` for the extras |
| commands vanish inside a filterscript | `#define FILTERSCRIPT` missing before the include | define it first so `PC_Init` hooks the FS init |

## Verification
```bash
pawncc -i./includes -d3 -O1 -;+ -(+ -ogamemodes/main.amx gamemodes/main.pwn 2>&1 | tail -2
```
Expected: `Header size: ...` followed by `0 Errors`. Then check no `printf`-style formats slipped in:

```bash
grep -rn "sscanf(params" gamemodes | grep -c '"%'
```
Expected output: `0`.

Runtime probe with the server up: `/setmoney 999 5` prints `No such player online.`, `/setcash` (the alias) prints the usage line, and `/nosuchcmd` prints `Unknown command. Try /help.`.

## Sources (2026)
- [katursis/Pawn.CMD](https://github.com/katursis/Pawn.CMD) — `cmd:`/`alias:`/`flags:` macros, both callbacks, `result == -1`, plugin install.
- [Pawn.CMD.inc source](https://raw.githubusercontent.com/katursis/Pawn.CMD/master/src/Pawn.CMD.inc) — macro expansion to `pc_cmd_`/`pc_alias_`, filterscript define.
- [Y-Less/sscanf README](https://github.com/Y-Less/sscanf/blob/master/README.md) — 2.15.1 specifier table, `q` is NPC name/id, `%` warning.
