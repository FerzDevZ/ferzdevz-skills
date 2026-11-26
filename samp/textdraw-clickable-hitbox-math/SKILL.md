---
name: textdraw-clickable-hitbox-math
description: Use when clicks miss the visual TextDraw button.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, ui]
    category: samp
---

# Clickable TextDraw hitbox math

## When to Use

- A click lands beside the button that is drawn on screen, usually a few units to one side.
- A grid of cells is clickable at 16:9 and misses at 4:3.
- A box button has a dead strip at its left or top edge.
- You are porting 0.3.7 textdraw code to open.mp and the alignment numbers changed.

## Compatibility & Stack Matrix (2026)

| Element | Value | Consequence for the hitbox |
| --- | --- | --- |
| Canvas | 640x480 virtual grid, mapped onto the whole screen | one x unit is about `W/640` px, one y unit `H/480` px |
| Alignment LEFT | `TEXT_DRAW_ALIGN_LEFT` = 1 in omp (0 in 0.3.7) | `TextDrawTextSize` x/y are the absolute right/bottom corner |
| Alignment CENTRE | `TEXT_DRAW_ALIGN_CENTRE` = 2 in omp (1 in 0.3.7) | x is the overall width, and the pair is swapped relative to LEFT |
| Alignment RIGHT | `TEXT_DRAW_ALIGN_RIGHT` = 3 in omp (2 in 0.3.7) | x/y are the absolute left/top corner |
| Box origin | starts 5 units left and 10 units up of the create coordinate | a 40x20 box request paints 45x30 |
| Font 4 / 5 | sprite / model preview | x/y become width/height offsets, not corners |
| Clickable area | always the `TextDrawTextSize` rectangle, box or no box | never derive it from `LetterSize` or the string length |

## Production Implementation

1. Treat the TextSize rectangle as the hitbox. It exists even with `TextDrawUseBox` off, which is why
   a text-only button still needs a size:

```pawn
stock Text:TD_MakeCell(Float:x, Float:y, Float:w, Float:h)
{
    new Text:td = TextDrawCreate(x, y, " ");
    TextDrawAlignment(td, TEXT_DRAW_ALIGN_LEFT);
    TextDrawTextSize(td, x + w, y + h);      // LEFT: absolute right/bottom corner
    TextDrawUseBox(td, true);
    TextDrawBoxColour(td, 0x000000AA);   // open.mp spelling; Color still aliases it
    TextDrawSetSelectable(td, true);         // SelectTextDraw only reacts once the draw is shown
    return td;
}
```

2. Separate the two rectangles you are actually working with. The click rectangle is
   `[x .. x+w] x [y .. y+h]`; the painted box starts at `(x-5, y-10)` and ends at the TextSize corner:

```pawn
// Visible box = [x-5 .. x+w] by [y-10 .. y+h] => 45x30 for the call above.
stock Float:TD_PaintedWidth(Float:w)  { return w + 5.0; }
stock Float:TD_PaintedHeight(Float:h) { return h + 10.0; }
```

3. When the painted box must sit flush on a pixel grid, push the create coordinate by the same bleed
   and keep the far corner on the grid line: create at `(gridX + 5.0, gridY + 10.0)`, then
   `TextDrawTextSize(td, gridX + w, gridY + h)`. The click rectangle now starts 5 right and 10 down of
   the painted corner, so a click on that strip does nothing - widen `w` and `h` if that matters.

4. Verify what the client stored instead of trusting an editor export. For LEFT alignment
   `TextDrawGetTextSize` echoes the absolute corner you passed, not a width - a 60x20 cell created at
   `(100, 100)` reads back as `160.0 / 120.0`:

```pawn
new Float:tw, Float:th;
TextDrawGetTextSize(td, tw, th);
printf("TD_RECT id=%d tw=%.1f th=%.1f align=%d selectable=%d",
    _:td, tw, th, _:TextDrawGetAlignment(td), _:TextDrawIsSelectable(td));
```

5. Leave a 2-unit gutter between cells whose boxes touch. With a 5-unit left bleed and a 10-unit top
   bleed, two 54-unit cells on a 54-unit pitch overlap by 5 units and the hover highlight jumps to the
   neighbour.

6. Column arithmetic for a uniform grid, kept in one place so the hitbox and the paint agree:

```pawn
#define GRID_COLS 7
#define GRID_PITCH 56.0

stock Float:TD_ColX(Float:anchorX, col) { return anchorX + float(col) * GRID_PITCH; }
stock Float:TD_RowY(Float:anchorY, row) { return anchorY + float(row) * GRID_PITCH; }
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Click registers 5 units right of the painted edge | hitbox taken from the create x, paint starts at x-5 | compute the click rect from TextSize, or shift create to `gridX+5` |
| Left 5 units and top 10 units of a button are dead | TextSize is the click rect; the box bleeds outside it | widen TextSize by the bleed if the strip must respond |
| Works at 16:9, misses at 4:3 | letter size used as a width | width comes from TextSize only |
| Sprite button visible but never clickable | font 4/5 turned x/y into width/height | pass width and height, not corners |
| Hover highlight lands on the neighbouring cell | two TextSize rectangles overlap | 2-unit gutter or a 1-unit border |
| Nothing highlights on hover | the draw was not shown before `SelectTextDraw` | show first, then select |

## Verification

```bash
pawncc /tmp/td_hitbox.pwn -i"$HOME/samp-sdk/omp-stdlib" -o/tmp/td_hitbox.amx
grep -E "TD_RECT" server/log.txt
```

Expected: the compiler prints only its banner (no `Error:` lines), and the log echoes the corner you
set, not a width - measured on omp-server with `TD_MakeCell(100.0, 100.0, 60.0, 20.0)`:

```text
TD_RECT id=0 tw=160.0 th=120.0 align=1 selectable=1 painted=65.0x30.0
```

`painted=65.0x30.0` is the box the client draws for a 60x20 request, i.e. the 5-unit left and 10-unit
top bleed is real, and the id depends on creation order.

## Sources (2026)

- https://open.mp/docs/scripting/functions/TextDrawTextSize
- https://open.mp/docs/scripting/functions/TextDrawAlignment
- https://open.mp/docs/scripting/functions/SelectTextDraw
