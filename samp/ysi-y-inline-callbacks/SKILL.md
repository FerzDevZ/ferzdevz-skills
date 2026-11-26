---
name: ysi-y-inline-callbacks
description: Use when a callback needs call-site state, not globals.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi, callbacks]
    category: samp
---

# y_inline: carry per-call state into a callback instead of a global array

`inline` declares a function inside a function and captures the enclosing locals as a closure.
`using inline` passes that closure to whatever expects a callback. Nothing is global, and two
players never share the same slot.

## When to Use

- A timer, dialog or HTTP callback needs `playerid` plus a local value (stage, item, price).
- The alternative is a per-player global array whose entries must be cleared on disconnect.
- You are porting YSI 4 `inline` code that uses `CallLocalFunction` string callbacks.
- A callback must run with an argument computed at call time, not read from state later.
- You want a dialog handler next to the code that opened it, instead of a public 400 lines away.

## Compatibility & Stack Matrix (2026)

| Item | Value | Notes |
| --- | --- | --- |
| Include | `<YSI_Coding\y_inline>` | YSI 5.x, pulls in the indirection layer |
| Keyword | `inline Name()` inside a function | anonymous `inline ()` is allowed for a one-shot |
| Passing | `using inline Name` | resolves the closure at the call site |
| Receiver | parameter tagged `Callback:` | old-style `Func:` signatures still link |
| Const form | `inline const Name()` | captured values are not written back |
| Timers | `Timer_CreateCallback` from y_inline_timers | time, then call count (0 = forever) |
| Dialogs | `Dialog_ShowCallback` from YSI_Dialogs | callback replaces `OnDialogResponse` |
| Public reuse | `using public Handler<iiiis>` | adapts an existing public to the signature |
| Plugin | none | script-side only, works on open.mp and SA-MP |
| Cost | one generated function per inline | visible in `.amx` size, not in warnings |

`SetTimerEx` cannot take an inline: its first argument is a function name string. Use the
y_inline timer wrapper, or `y_timers` `defer` around a named function.

## Production Implementation

1. Include the header once, in the file that owns the code, and keep the inline body short.
   Anything longer than a screen belongs in a normal function the inline calls:

```pawn
#include <YSI_Coding\y_inline>

new gBonusStage[MAX_PLAYERS];
```

2. Declare the inline at the end of the function, after the values it captures are final. The
   closure is created where the `inline` sits, so a variable assigned later is not seen:

```pawn
stock StartBonus(playerid, stage, amount)
{
    printf("BONUS start stage=%d amount=%d", stage, amount);
    inline Announce()
    {
        new msg[96];
        format(msg, sizeof msg, "Stage %d complete, +$%d", stage, amount);
        SendClientMessage(playerid, 0xFFFFFFFF, msg);
        gBonusStage[playerid] = stage + 1;
        printf("BONUS done stage=%d amount=%d", stage, amount);
    }
    Announce();                       // run once now, with the captured values
    return 1;
}
```

3. Pass it instead of calling it when the API owns the timing: hand the inline over with
   `using inline Tick` and let the y_inline timer wrapper take the interval and a call count
   (0 means forever). That count - not a forever/once boolean - is the most common mistake:

```pawn
stock ArmBonus(playerid, stage, minutes)
{
    inline Tick()
    {
        if (!IsPlayerConnected(playerid)) return;    // slot may be recycled
        gBonusStage[playerid]++;
        SendClientMessage(playerid, 0xFFFFFFAA, "Bonus tick");
    }
    Timer_CreateCallback(using inline Tick, minutes * 60000, 0);
    return 1;
}
```

4. Use `inline const` when the inline must not write captured state back. It is cheaper and
   makes the intent explicit: a read-only snapshot, not a live binding.

5. Keep one inline per purpose and give it a meaningful name. Two anonymous inlines in the same
   function are legal but unreadable in a stack trace, and the generated symbol is what a crash
   log shows you.

6. Guard the top of every inline that outlives the call: `IsPlayerConnected` for player work,
   and a version check for anything that may have been reset. The closure keeps a copy of
   `playerid` after the player has left, exactly like a global would.

7. Do not capture large arrays. Each inline copies the captured frame; a 4 KB buffer captured
   per call site is 4 KB of AMX data and a copy per invocation. Capture the index, read the
   array inside.

8. Read the `.amx` size before and after converting a feature, and record both numbers in the
   commit message. That is the only reliable signal that the closure machinery did not get
   duplicated per player.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Callback fires with a stale player | closure kept `playerid` after disconnect | `IsPlayerConnected` first line |
| Timer runs forever | count argument passed as 1 meaning "once" | count 0 = forever; pass 1 for once |
| Captured value never updates | `inline const` used, or reassigned after `inline` | declare as `inline`, assign before it |
| Compile error on `using inline` | argument is a plain function or a string | pass a named inline, not a name string |
| AMX grows per feature | big arrays captured, or inline duplicated | capture indices, move logic out |
| Wrong handler runs | two inlines with similar names in one file | name per feature, keep one per action |
| Works in test, dies on reconnect | state in the closure instead of the player | re-create the inline on connect |

## Verification

Compile with warnings as a gate, then confirm the inline actually ran exactly once per call:

```bash
pawncc gamemodes/rp.pwn -i./includes -o gamemodes/rp.amx -;+ -(+ -d3 2> /tmp/build.log
grep -cE ": (error|warning) " /tmp/build.log
grep 'BONUS' server/log.txt | tail -2
```

```text
0
BONUS start stage=1 amount=500
BONUS done stage=1 amount=500
```

Zero diagnostics is the pass for the syntax. Then measure the cost of the closure itself, which
must be a one-off per feature and not per player:

```bash
stat -c '%s' gamemodes/rp.amx
git stash list >/dev/null && echo "record this size in the commit message"
```

```text
1842
```

Run the same build twice: the size must be identical. A size that differs between builds means
generated inline symbols are not stable, which usually points at an inline declared inside a
macro or a loop.

## Sources (2026)

- https://github.com/pawn-lang/YSI-Includes/blob/5.x/YSI_Coding/y_inline/quick-start.md
- https://github.com/pawn-lang/YSI-Includes/blob/5.x/YSI_Coding/y_inline/features.md
- https://github.com/pawn-lang/YSI-Includes/blob/5.x/YSI_Coding/y_inline/faqs.md
