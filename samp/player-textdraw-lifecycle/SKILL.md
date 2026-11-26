---
name: player-textdraw-lifecycle
description: Use when PlayerTextDraw panels leak slots on reopen.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, ui]
    category: samp
---

# PlayerTextDraw lifecycle

## When to Use

- A panel opens empty the second time, or draws nothing after the 250th reopen.
- A panel is still on screen after death, respawn or a teleport.
- Closing a panel leaves the mouse cursor captured and the player cannot shoot.
- You need a per-player UI budget that survives an inventory, a HUD and a dialog.

## Compatibility & Stack Matrix (2026)

| Concern | 0.3.7 | open.mp 2026 | Rule |
| --- | --- | --- | --- |
| Created per player | 256 | 256 | keep under about 200 live, the rest is headroom |
| Created server-wide | 2048 | 2048 | global draws also count against the client's 2048 |
| Shown at once, one client | 2048 + 256 | 2048 + 256 | a player sees the global pool plus their own 256 |
| Handle type | `PlayerText:` | `PlayerText:` | never store it in an untagged `new` |
| After destroy | stale number | `IsValidPlayerTextDraw` returns false | reset to `INVALID_PLAYER_TEXT_DRAW` (`0xFFFF`) |
| On disconnect | destroyed by the server | destroyed by the server | your array still holds dead handles, reset it |
| String length | 1024 chars | 1024 chars | 255 is the safe cap once colour codes are used |

## Production Implementation

1. Own every handle in one array and make the build idempotent, so reopening can never double the count:

```pawn
#define PANEL_CELLS 12

new PlayerText:g_Cell[MAX_PLAYERS][PANEL_CELLS];
new bool:g_PanelOpen[MAX_PLAYERS];

stock Panel_Destroy(playerid)
{
    for (new i = 0; i < PANEL_CELLS; i++)
    {
        if (IsValidPlayerTextDraw(playerid, g_Cell[playerid][i]))
            PlayerTextDrawDestroy(playerid, g_Cell[playerid][i]);
        g_Cell[playerid][i] = INVALID_PLAYER_TEXT_DRAW;
    }
    g_PanelOpen[playerid] = false;
    return 1;
}

stock Panel_Build(playerid)
{
    Panel_Destroy(playerid);                 // idempotent: a rebuild never doubles
    for (new i = 0; i < PANEL_CELLS; i++)
    {
        new Float:y = 120.0 + float(i) * 12.0;
        new PlayerText:td = CreatePlayerTextDraw(playerid, 40.0, y, " ");
        PlayerTextDrawLetterSize(playerid, td, 0.2, 1.0);
        PlayerTextDrawTextSize(playerid, td, 140.0, y + 10.0);
        PlayerTextDrawAlignment(playerid, td, TEXT_DRAW_ALIGN_LEFT);
        PlayerTextDrawUseBox(playerid, td, true);
        PlayerTextDrawBoxColour(playerid, td, 0x000000AA);
        PlayerTextDrawSetSelectable(playerid, td, true);
        g_Cell[playerid][i] = td;
    }
    return 1;
}
```

2. Show and select in one place. `SelectTextDraw` only responds to draws that are already shown:

```pawn
stock Panel_Open(playerid)
{
    if (g_PanelOpen[playerid]) return 0;
    if (!IsValidPlayerTextDraw(playerid, g_Cell[playerid][0])) Panel_Build(playerid);
    for (new i = 0; i < PANEL_CELLS; i++) PlayerTextDrawShow(playerid, g_Cell[playerid][i]);
    g_PanelOpen[playerid] = true;
    SelectTextDraw(playerid, 0xFFFFFFAA);
    return 1;
}
```

3. Close releases the cursor. ESC never reaches `OnPlayerClickPlayerTextDraw`; it arrives in the global
   callback as `INVALID_TEXT_DRAW`:

```pawn
stock Panel_Close(playerid)
{
    if (!g_PanelOpen[playerid]) return 0;
    for (new i = 0; i < PANEL_CELLS; i++) PlayerTextDrawHide(playerid, g_Cell[playerid][i]);
    g_PanelOpen[playerid] = false;
    CancelSelectTextDraw(playerid);
    return 1;
}

public OnPlayerClickTextDraw(playerid, Text:clickedid)
{
    if (clickedid == INVALID_TEXT_DRAW) Panel_Close(playerid);   // ESC
    return 0;
}
```

4. Tie the panel to the player's life. Nothing hides a textdraw on death, and the server frees the slots
   on disconnect while your handles stay stale:

```pawn
public OnPlayerDeath(playerid, killerid, WEAPON:reason)   // 0.3.7 declared `reason` untagged
{
    Panel_Close(playerid);
    return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
    Panel_Destroy(playerid);                 // reset handles, do not rebuild later
    return 1;
}
```

5. Make a leak measurable instead of invisible. Budget the 256 first: 73 live slots is fine, four
   simultaneous 60-cell panels are not.

```pawn
stock Panel_LiveCount(playerid)
{
    new n;
    for (new i = 0; i < PANEL_CELLS; i++)
        if (IsValidPlayerTextDraw(playerid, g_Cell[playerid][i])) n++;
    return n;
}

printf("TD_LIFE player=%d open=%d cells=%d", playerid, _:g_PanelOpen[playerid], Panel_LiveCount(playerid));  // from /tdlife
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Panel empty on the second open | handles destroyed or overwritten, draws never rebuilt | rebuild when `IsValidPlayerTextDraw` is false |
| Live count doubles per reopen | new set created, old set never destroyed | `Panel_Destroy` at the top of `Panel_Build` |
| Draws appear from a previous session | handles reused after reconnect | reset in `OnPlayerDisconnect`, build on open |
| Cursor stuck after close, player cannot aim | `CancelSelectTextDraw` skipped | one close path that always cancels |
| ESC does nothing | handler only looks at `OnPlayerClickPlayerTextDraw` | handle `INVALID_TEXT_DRAW` in `OnPlayerClickTextDraw` |
| Panel still visible when dead | no teardown event | close in `OnPlayerDeath`, reopen on spawn |
| Creates start failing late in a session | 256 per-player cap reached | budget slots, destroy on close, watch the live count |

## Verification

```bash
pawncc /tmp/td_life.pwn -i"$HOME/samp-sdk/omp-stdlib" -o/tmp/td_life.amx
grep -c "CreatePlayerTextDraw" gamemodes/panel.pwn
grep -c "PlayerTextDrawDestroy" gamemodes/panel.pwn
```

Expected: no `Error:` or `Warning:` lines, and the two counts within one - a growing gap means every open
leaks. Three open/close cycles must leave `/tdlife` at `TD_LIFE player=0 open=0 cells=12`, and a
reconnect must leave it at `cells=0` before the first reopen.

## Sources (2026)

- https://open.mp/docs/scripting/resources/textdraws
- https://open.mp/docs/scripting/functions/PlayerTextDrawDestroy
- https://open.mp/docs/scripting/functions/IsValidPlayerTextDraw
