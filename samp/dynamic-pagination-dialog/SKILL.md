---
name: dynamic-pagination-dialog
description: Use when a dialog list is too long for one page.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ui, dialog, pagination]
    category: samp
---

# Page a list by absolute index, never by the row the client sends back

A dialog with 400 rows is one long scroll, and the `listitem` it returns is a row on
the page you drew, not an id. Pagination is the page plus an immutable snapshot of
the ids: without it the selection shifts whenever the list changes between pages.

## When to Use

- A house, vehicle or inventory list has more rows than a player can scan.
- The same `listitem` selects different things depending on which page is open.
- A `TABLIST_HEADERS` row loses its last column because the row is over 256 chars.
- Not for validating who sent the response — that is `dialog-spoofing-validation`.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.6.x | `GetPlayerDialogID`, `HidePlayerDialog`, 32768 dialog ids |
| SA-MP server | 0.3.7-R5 | no `GetPlayerDialogID`; track the pending id yourself |
| Dialog styles | `DIALOG_STYLE_LIST`, `DIALOG_STYLE_TABLIST_HEADERS` | tablist: 4 columns, 128 chars per column, 256 per row |
| Response codes | `DIALOG_RESPONSE_LEFT` = 1, `DIALOG_RESPONSE_RIGHT` = 0 | left button or ENTER, right button or ESC |
| `listitem` | 0-based row, `-1` for non-list styles | never a global index |

## Production Implementation

1. Define the response constants defensively. SA-MP headers do not ship them and
   open.mp's player include may already define the same names, so guard the
   definition instead of redefining it:

```pawn
#if !defined DIALOG_RESPONSE_LEFT
    #define DIALOG_RESPONSE_LEFT   (1)   // left button or ENTER
#endif
#if !defined DIALOG_RESPONSE_RIGHT
    #define DIALOG_RESPONSE_RIGHT  (0)   // right button or ESC
#endif

#define PAGE_SIZE          12
#define MAX_PAGE_ENTRIES   512
#define DIALOG_HOUSELIST   4100
```

2. Keep the page and a snapshot of ids per player. The snapshot is what makes the
   page stable: re-sorting the DB between two views must not change what row 3 means.

```pawn
enum E_Page
{
    pgPage,
    pgCount,
    pgIds[MAX_PAGE_ENTRIES]
};
new g_Page[MAX_PLAYERS][E_Page];
```

3. Fill the snapshot once when the list opens (`LoadHouseIds(g_Page[playerid][pgIds], MAX_PAGE_ENTRIES)`),
   reset the page to 0, then render only a slice. Clamp the page so a shrinking list
   cannot point past the end. Render items and navigation rows into the body while
   recording the row index where each navigation entry landed — never assume they
   come first or last.

```pawn
forward GetHouseLabel(houseid, label[], size);   // project helper: cached house caption
forward LoadHouseIds(dest[], max);               // project helper: SELECT id FROM houses

stock ShowHousePage(playerid)
{
    new body[2048], label[80], len, rows, rowPrev = -1, rowNext = -1;
    new offset = g_Page[playerid][pgPage] * PAGE_SIZE;
    new total  = g_Page[playerid][pgCount];

    for (new i = 0; i < PAGE_SIZE && offset + i < total; i++)
    {
        GetHouseLabel(g_Page[playerid][pgIds][offset + i], label, sizeof label);
        len += format(body[len], sizeof body - len, "%s\n", label);
        rows++;
    }
    if (g_Page[playerid][pgPage] > 0)
    {
        rowPrev = rows++;
        len += format(body[len], sizeof body - len, "« Previous page\n");
    }
    if (offset + PAGE_SIZE < total)
    {
        rowNext = rows++;
        len += format(body[len], sizeof body - len, "Next page »\n");
    }

    new title[64];
    format(title, sizeof title, "Houses %d-%d of %d", offset + 1, offset + rows, total);
    ShowPlayerDialog(playerid, DIALOG_HOUSELIST, DIALOG_STYLE_LIST, title, body, "Open", "Close");
    return 1;
}
```

4. Translate the response with the same arithmetic the renderer used, and re-check
   the bounds against the snapshot instead of trusting the client row.

```pawn
public OnDialogResponse(playerid, dialogid, response, listitem, inputtext[])
{
    if (dialogid != DIALOG_HOUSELIST) return 0;
    if (response == DIALOG_RESPONSE_RIGHT) return 1;               // Close
    if (response != DIALOG_RESPONSE_LEFT) return 1;                // no third value

    new offset = g_Page[playerid][pgPage] * PAGE_SIZE;
    new total  = g_Page[playerid][pgCount];
    new rows   = total - offset;
    if (rows > PAGE_SIZE) rows = PAGE_SIZE;

    if (listitem == rows && g_Page[playerid][pgPage] > 0)          // « Previous
    {
        g_Page[playerid][pgPage]--;
        return ShowHousePage(playerid);
    }
    if (listitem == rows + ((g_Page[playerid][pgPage] > 0) ? 1 : 0)  // Next »
        && offset + PAGE_SIZE < total)
    {
        g_Page[playerid][pgPage]++;
        return ShowHousePage(playerid);
    }
    if (listitem < 0 || listitem >= rows) return 1;                // forged row

    new abs = offset + listitem;
    if (abs < 0 || abs >= total) return 1;
    return OpenHouse(g_Page[playerid][pgIds][abs]);
}
```

5. Keep one dialog id per list, and decide the cancel path explicitly: reset to page
   0 in the open path or store the last page per feature. Reusing `DIALOG_HOUSELIST`
   for the garage makes the arithmetic read the wrong snapshot.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Clicking row 3 opens the wrong house | `listitem` treated as a global id | add the page offset, then index the snapshot |
| "Next" jumps back to page 1 | page reset inside `OnDialogResponse` | keep `pgPage` per player, only the renderer clamps |
| Selection changes between pages | live DB list re-queried per page | fill `pgIds` once, page over the snapshot |
| Last page opens an out-of-range id | remainder not clamped | compare `abs` with `total` before use |
| Nav rows select items on page 1 | nav rows counted as items | record `rowPrev`/`rowNext` in the renderer |
| Tablist truncates the price column | row over 256 chars, or a 5th column | shorten labels, keep 4 columns |
| ESC after paging reopens at page 0 | cancel path ignores stored page | reset or restore explicitly in the open path |

## Verification

```bash
pawncc -i include -d3 pagination.pwn -o pagination.amx
```

- Zero errors, zero warnings; a `213` tag mismatch on `listitem` means it was read
  as a tagged value.
- `/houses` with 250 rows titles itself `Houses 1-12 of 250`; the last page reads
  `Houses 241-250 of 250` with ten rows plus `« Previous page`.
- Every row on page 3 opens a distinct house; `listitem = 13` on a non-last page advances.

## Sources (2026)

- https://open.mp/docs/scripting/callbacks/OnDialogResponse
- https://open.mp/docs/scripting/resources/dialogstyles
- https://open.mp/docs/scripting/resources/limits
