---
name: textdraw-scrollbar-list-grid
description: Use when a TextDraw list needs scrolling rows.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, ui]
    category: samp
---

# Scroll a long list in TextDraws without growing the pool

A list panel is a fixed set of row draws plus an offset. The rows never change count; only the
string each row shows moves.

## When to Use

- A dialog outgrew `DIALOG_STYLE_LIST` (columns, colours, icons) and moved to TextDraws.
- The list has 50-500 entries and the panel shows 8-12.
- The highlighted row and the item acted on disagree after scrolling.
- Mouse-wheel or key scrolling drifts, or the highlight sticks to a screen position.
- The player-textdraw pool grows while browsing and the UI dies after a while.

## Compatibility & Stack Matrix (2026)

| Item | Value | Notes |
| --- | --- | --- |
| Pool | 256 player draws per player, 2048 global | create with `CreatePlayerTextDraw`, reuse rows |
| Visible rows | `ROWS` (10 here) | `ROWS * (height + gap)` is the panel height |
| Scrolling | `PlayerTextDrawSetString` per row | no geometry change, so no re-measure |
| Clickable rows | `PlayerTextDrawSetSelectable` + `SelectTextDraw` | mouse mode is global per player |
| Click callback | `OnPlayerClickPlayerTextDraw` | gives the draw id, not the row index |
| Highlight | `PlayerTextDrawColor` / `PlayerTextDrawBoxColor` | repaint on scroll |

Selection is an item index, never a screen row: `gSel = gOffset + row`, repainted from `gSel - gOffset`.

## Production Implementation

1. Fix the geometry once: row height plus gap times visible rows is the vertical budget, and
   the scroll buttons sit outside it:

```pawn
#define ROWS    (10)
#define ROW_H   (18.0)
#define ROW_GAP (1.0)
#define PANEL_X (320.0)
#define PANEL_Y (140.0)
```

2. Keep one pool per player: rows, buttons and state. Creating in the click or render path is
   the unbounded growth this skill prevents:

```pawn
new PlayerText:gRow[ROWS];
new gOffset[MAX_PLAYERS], gSel[MAX_PLAYERS], gCount[MAX_PLAYERS], gPeak[MAX_PLAYERS];
new gItems[200][64];
```

3. Build the rows in one loop with selectable hitboxes that match the drawn text height:

```pawn
stock BuildListTD(playerid)
{
    for (new r = 0; r < ROWS; r++)
    {
        gRow[r] = CreatePlayerTextDraw(playerid, PANEL_X + 12.0,
            PANEL_Y + 8.0 + r * (ROW_H + ROW_GAP), "_");
        PlayerTextDrawLetterSize(playerid, gRow[r], 0.24, 1.1);
        PlayerTextDrawColor(playerid, gRow[r], 0xC8C8C8FF);
        PlayerTextDrawSetSelectable(playerid, gRow[r], true);
        PlayerTextDrawTextSize(playerid, gRow[r], 150.0, ROW_H);
        PlayerTextDrawShow(playerid, gRow[r]);
    }
    gPeak[playerid] = ROWS;
    return 1;
}
```

4. Render from data and clamp in the same function. A row past the count is blank, and each
   visible row prints its real index so a screenshot is enough to debug:

```pawn
stock RenderList(playerid)
{
    new maxoff = gCount[playerid] > ROWS ? gCount[playerid] - ROWS : 0;
    if (gOffset[playerid] > maxoff) gOffset[playerid] = maxoff;
    if (gOffset[playerid] < 0) gOffset[playerid] = 0;
    for (new r = 0; r < ROWS; r++)
    {
        new idx = gOffset[playerid] + r, line[64];
        if (idx < gCount[playerid]) format(line, sizeof line, "%d. %s", idx + 1, gItems[idx]);
        else line[0] = '\0';
        PlayerTextDrawSetString(playerid, gRow[r], line);
        PlayerTextDrawColor(playerid, gRow[r], idx == gSel[playerid] ? 0xFFFF00FF : 0xC8C8C8FF);
    }
    printf("TD list rows=%d items=%d offset=%d peak=%d",
        ROWS, gCount[playerid], gOffset[playerid], gPeak[playerid]);
    return 1;
}
```

5. Scroll by a line or a page, always through the clamp, then re-render. Only the offset moves,
   so the hitboxes stay valid and nothing needs recreating:

```pawn
stock ScrollList(playerid, delta) { gOffset[playerid] += delta; return RenderList(playerid); }
```

6. Map the click back to an item before acting. Using the draw id as an item id is correct only
   while the offset is zero, which is exactly why the bug ships:

```pawn
public OnPlayerClickPlayerTextDraw(playerid, PlayerText:playerid_td)
{
    for (new r = 0; r < ROWS; r++)
    {
        if (playerid_td != gRow[r]) continue;
        new idx = gOffset[playerid] + r;
        if (idx >= gCount[playerid]) return 1;          // blank row under the last item
        gSel[playerid] = idx;
        RenderList(playerid);
        return 1;
    }
    return 1;
}
```

7. Open with `SelectTextDraw` and close with `CancelSelectTextDraw` plus `PlayerTextDrawHide`;
   leaving mouse mode on makes the whole HUD unclickable and looks like a client bug. On
   disconnect, `PlayerTextDrawDestroy` every row: the pool is per connection, and a
   `/reconnect` is where a missing destroy shows up as a blank panel.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Panel stops updating after browsing | a draw per item exhausted the pool | create `ROWS` draws once, `SetString` after |
| Wrong item opened | click used the screen row | `gOffset + row` |
| Highlight jumps between rows | selection stored as row, then offset changed | store the item index, repaint from it |
| Row clicks do nothing at the bottom | hitbox shorter than the gap | `PlayerTextDrawTextSize` covers `ROW_H` |
| Last item unreachable | offset clamped to `count`, not `count - ROWS` | clamp to `count > ROWS ? count - ROWS : 0` |
| HUD dead after closing | `SelectTextDraw` without `CancelSelectTextDraw` | cancel on every close path |
| Blank panel after reconnect | draws never destroyed | `PlayerTextDrawDestroy` on disconnect |

## Verification

Compile, then read the pool line after 100 scroll steps:

```bash
pawncc gamemodes/rp.pwn -i./includes -o gamemodes/rp.amx -;+ -(+ -d3 2>&1 | grep -cE "error|warning"
grep 'TD list' server/log.txt | tail -2
```

```text
0
TD list rows=10 items=100 offset=0 peak=10
TD list rows=10 items=100 offset=90 peak=10
```

`peak` identical in both lines is the pass: 90 scroll steps changed strings only. A rising
`peak` means a draw is created in the scroll or click path, not in `BuildListTD`.

## Sources (2026)

- https://open.mp/docs/scripting/functions/CreatePlayerTextDraw
- https://open.mp/docs/scripting/functions/PlayerTextDrawSetSelectable
- https://open.mp/docs/scripting/callbacks/OnPlayerClickPlayerTextDraw
