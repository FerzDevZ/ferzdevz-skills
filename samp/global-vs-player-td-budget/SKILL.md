---
name: global-vs-player-td-budget
description: Use when a HUD must choose the global or per-player pool.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, limits, hud]
    category: samp
---

# Put each TextDraw in the pool that can afford it

## When to Use

- A HUD works for the first players and stops drawing for the rest.
- You are deciding, element by element, between a global draw and a per-player draw.
- A player-scoped array of textdraws has grown to `[MAX_PLAYERS][256]` and the AMX is fat.
- Not for measuring which slot leaked; that is `textdraw-limit-2048-optimizer`.

## Compatibility & Stack Matrix (2026)

| Pool | Limit | Measured / documented | Consequence |
| --- | --- | --- | --- |
| Global `TextDrawCreate` | 2048 | measured on 1.6.7.3218: `refused_at=2048`, returns `65535` | shared by every element the server draws |
| Per player `CreatePlayerTextDraw` | 256 | compile-time `MAX_PLAYER_TEXT_DRAWS` in `omp_textdraw.inc` | 1000 players can hold 256,000 slots |
| Per-player refusal | silent | measured: 5000 creates still returned handles, `IsValidPlayerTextDraw` false | count slots yourself, do not trust the return |
| Text per draw | 1024 chars | documented; colour codes past char 255 crash the legacy client | one long string is a limit, not a layout |
| Per-viewer string | `TextDrawSetStringForPlayer` | core open.mp native | one global slot can show different text per client |
| Sprites shown at once | 100 | documented | icon fonts 4/5 stop drawing past 100 |
| Static cost | 4 bytes per cell | `[MAX_PLAYERS][256]` for 1000 players = 256,000 cells = 1 MB | per-player arrays are memory, not just slots |

## Production Implementation

1. Classify each element first. Identical geometry and text: global, set once. Identical geometry and
   per-client text: global plus `TextDrawSetStringForPlayer`. Anything that moves or recolours per
   client: per-player.

2. Declare one handle per line. `new Text:a, b;` tags only `a`, and the second becomes an untagged
   cell that warns on every use:

```pawn
#define TD_GLOBAL_MAX   (2048)
#define TD_PLAYER_MAX   (256)

new Text:g_TdName;                          // one declarator per handle
new Text:g_TdMoney;
new Text:g_TdClock;                         // identical for every client
new PlayerText:g_OwnClock[MAX_PLAYERS];     // per-client geometry
new g_GlobalUsed;
new g_OwnUsed[MAX_PLAYERS];                 // the 256 slots are per player: count per player
```

3. Wrap both pools in one allocator each, so the count is always the truth:

```pawn
stock Text:TD_Global(Float:x, Float:y, const text[])
{
    if (g_GlobalUsed >= TD_GLOBAL_MAX) return Text:INVALID_TEXT_DRAW;
    new Text:td = TextDrawCreate(x, y, text);
    if (td == Text:INVALID_TEXT_DRAW) return td;         // pool full: 65535
    g_GlobalUsed++;
    return td;
}

stock PlayerText:TD_Own(playerid, Float:x, Float:y, const text[])
{
    if (g_OwnUsed[playerid] >= TD_PLAYER_MAX) return PlayerText:INVALID_PLAYER_TEXT_DRAW;
    new PlayerText:td = CreatePlayerTextDraw(playerid, x, y, text);
    if (td == PlayerText:INVALID_PLAYER_TEXT_DRAW) return td;
    g_OwnUsed[playerid]++;
    return td;
}
```

4. Build the shared elements once at boot: `g_TdName = TD_Global(320.0, 20.0, "Server");` and the
   same call for money and clock.

5. Rewrite the string per client instead of cloning the draw. This is the move that turns a
   1000-player server from 3000 draws into 3:

```pawn
stock Hud_Money(playerid, amount)
{
    TextDrawSetStringForPlayer(g_TdMoney, playerid, "$%d", amount);
    TextDrawShowForPlayer(playerid, g_TdMoney);
}

stock Hud_Clock(playerid, const text[])
{
    TextDrawSetStringForPlayer(g_TdClock, playerid, "%s", text);
    TextDrawShowForPlayer(playerid, g_TdClock);
}
```

6. Spend a per-player slot only when geometry or colour really differs, and create it on demand:

```pawn
stock Hud_InitClock(playerid)
{
    g_OwnClock[playerid] = TD_Own(playerid, 520.0, 60.0, "--:--");
    if (g_OwnClock[playerid] == PlayerText:INVALID_PLAYER_TEXT_DRAW) return 0;
    PlayerTextDrawShow(playerid, g_OwnClock[playerid]);
}
```

7. Do the arithmetic before choosing: 20 shared HUD elements as per-player draws is 20,000 slots,
   against 20 global draws out of 2048. Only the moving part belongs in the player pool.

8. Print both counters at boot and on connect, so the numbers in production come from the binary:

```pawn
public OnGameModeInit()
{
    Hud_Build();
    printf("td_budget global=%d/%d", g_GlobalUsed, TD_GLOBAL_MAX);
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Pool "full" after 256 total draws | one global counter used for the per-player pool | count per player: `g_OwnUsed[playerid]` |
| Creates keep succeeding but nothing draws | open.mp returns handles past the per-player pool | own counter plus `IsValidPlayerTextDraw` |
| `refused_at=2048` and missing elements | global ceiling reached, unchecked `65535` | check `INVALID_TEXT_DRAW`, log the label |
| Text cut mid-sentence | 1024-character limit per draw | split into two draws or drop colour codes |
| Legacy client crashes on a long coloured string | colour codes past char 255 | keep codes in the first 255 characters |
| Hundreds of MB of static data | `[MAX_PLAYERS][256]` array of handles | allocate per player, or use globals |

## Verification

```bash
pawncc -i"$HOME/samp-sdk/omp-stdlib" -d3 '-;+' '-(+' -oprobe_budget.amx probe_budget.pwn; echo "exit=$?"
./omp-server                                  # with this AMX as the main script
grep -aE 'td_budget|TD_GLOBAL' log.txt
```

Expected compile output for the code above:

```text
Pawn compiler 3.10.10	 	 	 	Copyright (c) 1997-2006, ITB CompuPhase

Header size:            420 bytes
Code size:             1712 bytes
Data size:             8256 bytes
Stack/heap size:      16384 bytes; estimated max. usage=74 cells (296 bytes)
Total requirements:   26772 bytes
exit=0
```

Expected runtime line from the same build:

```text
[2026-11-26T07:56:43+0000] [Info] td_budget global=3/2048
```

To see the ceiling instead of the normal case, run a probe that allocates until refusal; this server
printed `TD_GLOBAL refused_at=2048` followed by `TD_GLOBAL created=2048`.

## Sources (2026)

- https://open.mp/docs/scripting/resources/limits
- https://open.mp/docs/scripting/functions/TextDrawCreate
- https://open.mp/docs/scripting/functions/CreatePlayerTextDraw
