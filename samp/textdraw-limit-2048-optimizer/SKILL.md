---
name: textdraw-limit-2048-optimizer
description: Use when the TextDraw pool runs near 2048 or 256.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, limits]
    category: samp
---

# TextDraw pool: audit the 2048 and 256 ceilings

## When to Use

- Draws created late at boot never appear, with no error in the console.
- `TextDrawCreate` returns a handle that is not valid and you cannot tell which call was refused.
- A HUD that worked with 100 players stops drawing for the 300th.
- You inherited an editor export with hundreds of unused draws.

## Compatibility & Stack Matrix (2026)

| Limit | Value | Measured / documented | Consequence |
| --- | --- | --- | --- |
| Global textdraws created server-side | 2048 | measured: create #2049 returns `65535` (`INVALID_TEXT_DRAW`) | every static HUD element is a permanent slot |
| Player textdraws created per player | 256 | documented in the limits table | a 49-cell inventory costs 49 of 256 |
| Shown at once, one client | 2048 + 256 | documented | the client can show both pools together |
| Sprites shown at once | 100 | documented | icon fonts 4/5 stop drawing past 100 |
| String length | 1024 chars | documented; the omp include docstring still says 800 | colour codes past char 255 crash the legacy client |
| Slot reuse | immediate | measured: destroy id 100, next create returns 100 | destroying is a real fix, not a leak trade |

## Production Implementation

1. Never call `TextDrawCreate` directly. Route it through a registry that counts, so the pool number is
   always the truth:

```pawn
#define TD_MAX 2048

new Text:g_TD[TD_MAX];
new g_TDUsed;

stock Text:TD_New(Float:x, Float:y, const text[])
{
    if (g_TDUsed >= TD_MAX)
    {
        printf("TD_OVERFLOW refused='%s' used=%d", text, g_TDUsed);
        return INVALID_TEXT_DRAW;
    }
    new Text:td = TextDrawCreate(x, y, text);
    if (td == INVALID_TEXT_DRAW)          // server pool full: returns 65535, measured
        return INVALID_TEXT_DRAW;
    g_TD[g_TDUsed++] = td;
    return td;
}

stock TD_Free(Text:td)
{
    if (!IsValidTextDraw(td)) return 0;
    TextDrawDestroy(td);
    for (new i = 0; i < g_TDUsed; i++)
    {
        if (g_TD[i] == td)
        {
            g_TD[i] = g_TD[--g_TDUsed];    // swap-remove keeps the array dense
            break;
        }
    }
    return 1;
}

stock TD_Report(const label[])
{
    printf("TD_POOL %s used=%d/%d free=%d", label, g_TDUsed, TD_MAX, TD_MAX - g_TDUsed);
}
```

2. Print the report at boot and after building every screen, then read the number instead of guessing:

```pawn
public OnGameModeInit()
{
    // ... create the static HUD through TD_New ...
    TD_Report("boot");
    return 1;
}
```

3. Collapse per-player text into one global draw. `TextDrawSetStringForPlayer` rewrites the string for a
   single client, so a 1000-player server still uses one slot:

```pawn
new Text:g_Bag;

// boot: g_Bag = TD_New(20.0, 300.0, "Bag 0/0");
stock Bag_Show(playerid, used, cap)
{
    TextDrawSetStringForPlayer(g_Bag, playerid, "Bag %d/%d", used, cap);
    TextDrawShowForPlayer(playerid, g_Bag);
}
```

4. Move anything that must differ in geometry or colour per player into player textdraws; that trades a
   global slot for one of the 256 per player, which is the pool with headroom in most gamemodes.

5. Audit the source before running anything - the draw count is static in most codebases:

```bash
grep -c "TextDrawCreate(" gamemodes/*.pwn | sort -t: -k2 -n | tail -5
grep -c "CreatePlayerTextDraw(" gamemodes/*.pwn | sort -t: -k2 -n | tail -5
```

6. Budget: 2048 divided by 10 screens is 200 draws per screen. A screen that needs 400 is either two
   screens or a list that reuses 40 cells and swaps strings (`TextDrawSetString`).

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Late draws silently missing, console clean | 2049th create returned `65535`, unchecked | wrap creation, check for `INVALID_TEXT_DRAW`, log the label |
| Count drifts from the real pool | destroyed draws still counted, or direct calls bypass the registry | free through `TD_Free`, no raw `TextDrawCreate` |
| Pool fine at boot, full at runtime | per-open creation of panels | build once per player, hide instead of destroy |
| 101st sprite icon invisible | 100-sprite client limit | use font 1 glyphs or fewer sprite cells |
| String cut mid-sentence | 1024-char ceiling, 255 with colour codes | split into two draws or drop codes |
| Same label stored 500 times | one draw per player for identical text | one global draw plus `TextDrawSetStringForPlayer` |
| Editor export leaves dead draws | unused elements never removed | delete at source, re-measure with `TD_Report` |

## Verification

```bash
pawncc /tmp/td_pool.pwn -i"$HOME/samp-sdk/omp-stdlib" -o/tmp/td_pool.amx
grep -E "TD_POOL|TD_OVERFLOW" server/log.txt
```

Expected: no compiler errors, one `TD_POOL boot used=N/2048 free=2048-N` line, and zero `TD_OVERFLOW`
lines in normal play. Filling the pool through `TD_New` on omp-server produced this, which is what a
working registry looks like at the ceiling:

```text
TD_POOL boot used=2048/2048 free=0
TD_OVERFLOW refused='extra' used=2048
TD_PROBE over=65535 valid=0
TD_POOL after-free used=2047/2048 free=1
TD_PROBE reuse=100
```

`reuse=100` is the server handing back the id that `TD_Free` released, so freeing is what keeps a long
session alive; the `TD_OVERFLOW` line names the label that did not fit.

## Sources (2026)

- https://open.mp/docs/scripting/resources/limits
- https://open.mp/docs/scripting/functions/TextDrawCreate
- https://open.mp/docs/scripting/resources/textdrawsprites
