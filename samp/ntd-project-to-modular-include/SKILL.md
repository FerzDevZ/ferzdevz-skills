---
name: ntd-project-to-modular-include
description: Use when an NTD editor export must become an include.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, refactor, ntd]
    category: samp
---

# Turn an editor export into a reusable include

## When to Use

- Nick's TextDraw Editor exported a few hundred lines of `TextDrawCreate` into your gamemode.
- Two scripts include copies of the same exported block and they have drifted.
- You must rebuild the same HUD at boot, per player, or in a test world.
- The export is fixed data and the logic around it keeps changing.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| Editor export | `TextDrawCreate` plus style calls per element | one element is 8-12 lines, ids are implicit |
| Target | include with a data table plus one builder | a single `TextDrawCreate` call site |
| Global pool | 2048 draws | a 40-element export is 2% of it |
| String | 1024 chars per draw | one row holding a whole panel is a risk |
| Colour spelling | `TextDrawColour` | `TextDrawColor` is deprecated: warning 234, an error under `-E` |

## Production Implementation

1. Freeze the export. Copy it to `ntd_export.pwn`, commit it, and never hand-edit it: it is the
   source of truth for coordinates. Count what you are dealing with first:

```bash
grep -c 'TextDrawCreate(' ntd_export.pwn      # element count
grep -c 'TextDrawLetterSize(' ntd_export.pwn  # style calls to fold into rows
```

2. Each element is the same four lines: a `TextDrawCreate` with `Float:` coordinates, then letter
   size, colour and shadow calls. Turn each into one row of a static table, floats first.

3. Write the include with a guard, a row enum, the table and a module-private handle array:

```pawn
// ntd_hud.inc - NTD export turned into a reusable include
#if defined _ntd_hud_included
    #endinput
#endif
#define _ntd_hud_included

#define NTD_HUD_DRAWS   (3)
#define NTD_HUD_LEN     (48)

enum E_NtdDraw
{
    Float:ntdX,
    Float:ntdY,
    ntdText[NTD_HUD_LEN],
    ntdColour,
    Float:ntdLetterX,
    Float:ntdLetterY
};

static const gNtdRows[NTD_HUD_DRAWS][E_NtdDraw] =
{
    { 320.000, 20.000, "Server", 0xFFFFFFFF, 0.320, 0.960 },
    { 320.000, 42.000, "$0",     0xFFFFD700, 0.320, 0.960 },
    { 320.000, 64.000, "--:--",  0xFFE0E0E0, 0.320, 0.960 }
};

new Text:g_Ntd[NTD_HUD_DRAWS];
new bool:g_NtdBuilt;
```

4. Replace the exported call list with one loop, style calls in the same order as the export:

```pawn
stock Ntd_Count()
{
    return NTD_HUD_DRAWS;
}

stock Ntd_Build()
{
    if (g_NtdBuilt) return 1;
    for (new i = 0; i < NTD_HUD_DRAWS; i++)
    {
        g_Ntd[i] = Text:TextDrawCreate(gNtdRows[i][ntdX], gNtdRows[i][ntdY], gNtdRows[i][ntdText]);
        if (g_Ntd[i] == Text:INVALID_TEXT_DRAW) return 0;
        TextDrawLetterSize(g_Ntd[i], gNtdRows[i][ntdLetterX], gNtdRows[i][ntdLetterY]);
        TextDrawColour(g_Ntd[i], gNtdRows[i][ntdColour]);
        TextDrawSetShadow(g_Ntd[i], 0);
    }
    g_NtdBuilt = true;
    return 1;
}
```

5. Expose verbs and nothing else - show, hide, set text. A caller that needs more gets a new verb,
   so the include stays the only place that knows about draw indices:

```pawn
stock Ntd_Show(playerid)
{
    for (new i = 0; i < NTD_HUD_DRAWS; i++) TextDrawShowForPlayer(playerid, g_Ntd[i]);
    return 1;
}

stock Ntd_SetText(draw, const text[])
{
    if (draw < 0 || draw >= NTD_HUD_DRAWS) return 0;
    return _:TextDrawSetString(g_Ntd[draw], text);
}
```

6. Consume it with no numbers in sight: `#include "ntd_hud.inc"`, call `Ntd_Build()` once in
   `OnGameModeInit()`, then `Ntd_SetText(1, "$1500")` and `Ntd_Show(playerid)` per player.

7. When the editor is re-opened, re-export and diff only the table block, so the builder is never
   regenerated and a re-export cannot undo the structure:

```bash
diff <(sed -n '/gNtdRows/,/^};/p' old/ntd_hud.inc) <(sed -n '/gNtdRows/,/^};/p' new/ntd_hud.inc)
```

8. If the HUD must differ per client, the same table can feed `CreatePlayerTextDraw` (256 slots
   per player, not 2048).

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Gamemode crashes after a re-export | it still references `tdHud[7]` by index | expose verbs, keep handles inside the include |
| Hand tweaks vanish | the generator overwrites the include | regenerate only the table, review the diff |
| Text off by a few units after a spreadsheet pass | `320.000` became `320` | edit the table in the editor, not Sheets |
| `error 234: function is deprecated (symbol "TextDrawColor")` | the export uses the SA-MP spelling | rename to `TextDrawColour`, or define `SAMP_COMPAT` |
| Half the HUD missing at boot | `Ntd_Build` returned `0` on the 2049th draw | check `INVALID_TEXT_DRAW` and log the row |
| Panel text truncated | one row holds a string over 1024 chars | split into more rows, one per line |

## Verification

```bash
pawncc -i"$HOME/samp-sdk/omp-stdlib" -iincludes -d3 '-;+' '-(+' -oprobe_ntd.amx probe_ntd.pwn
echo "exit=$?"
grep -c 'TextDrawCreate(' includes/ntd_hud.inc
```

Expected - a clean build and exactly one create call site in the include:

```text
Pawn compiler 3.10.10	 	 	 	Copyright (c) 1997-2006, ITB CompuPhase

Header size:            444 bytes
Code size:             1840 bytes
Data size:              816 bytes
Stack/heap size:      16384 bytes; estimated max. usage=74 cells (296 bytes)
Total requirements:   19484 bytes
exit=0
1
```

A count above `1` means an exported create call survived the refactor.

## Sources (2026)

- https://open.mp/docs/scripting/resources/textdraws
- https://open.mp/docs/scripting/functions/CreatePlayerTextDraw
- https://open.mp/docs/scripting/functions/TextDrawCreate
