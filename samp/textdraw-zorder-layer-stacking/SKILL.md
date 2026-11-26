---
name: textdraw-zorder-layer-stacking
description: Use when a panel's text hides behind its own background.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, ui, z-order]
    category: samp
---

# Stack TextDraws by ID, because show order is not a layer

## When to Use

- A panel's label is invisible, or only appears after the panel is reopened.
- A language switch or a re-layout leaves the background above the text.
- You are building a HUD panel, dialog or radial menu and need a documented layer order.
- Not for picking the pool or counting slots; those are `global-vs-player-td-budget` and
  `textdraw-limit-2048-optimizer`.

## Compatibility & Stack Matrix (2026)

| Rule | Observed / documented | Consequence |
| --- | --- | --- |
| Draw order inside one pool | the client composites shown slots in slot order, one ordered pass | the highest ID is drawn last, on top |
| `TextDrawCreate` return | IDs start at 0 and increase | later creation means higher layer |
| `TextDrawShowForPlayer` / `TextDrawHideForPlayer` | toggles visibility only | show order never changes stacking |
| `TextDrawSetPos` | added in omp 1.1.0.2612 | moving a draw does not reorder it |
| `TextDrawDestroy` then create | the freed slot is reused at the end of the allocation order | a rebuilt element lands on top |
| Global pool vs per-player pool | two separate pools with separate ID spaces | cross-pool order is not scriptable |
| Selection highlight | drawn by the client for the selected draw | it always sits above your own layers |

## Production Implementation

1. Name the layers and create in that order. The enum is the contract; the creation calls must follow it:

```pawn
enum
{
    LAYER_SHADOW = 0,     // darkest, drawn first
    LAYER_PANEL,          // the panel body, covers the shadow except its offset edge
    LAYER_TEXT,           // always last
    LAYER_COUNT
};

new Text:g_Panel[LAYER_COUNT];

stock PanelCreate()
{
    g_Panel[LAYER_SHADOW] = TextDrawCreate(102.0, 102.0, " ");
    TextDrawUseBox(g_Panel[LAYER_SHADOW], true);
    TextDrawBoxColor(g_Panel[LAYER_SHADOW], 0x00000060);
    TextDrawTextSize(g_Panel[LAYER_SHADOW], 262.0, 192.0);
    TextDrawLetterSize(g_Panel[LAYER_SHADOW], 0.0, 0.0);

    g_Panel[LAYER_PANEL] = TextDrawCreate(100.0, 100.0, " ");
    TextDrawUseBox(g_Panel[LAYER_PANEL], true);
    TextDrawBoxColor(g_Panel[LAYER_PANEL], 0x1E1E1EC8);
    TextDrawTextSize(g_Panel[LAYER_PANEL], 260.0, 190.0);
    TextDrawLetterSize(g_Panel[LAYER_PANEL], 0.0, 0.0);

    g_Panel[LAYER_TEXT] = TextDrawCreate(112.0, 106.0, "Panel");
    TextDrawFont(g_Panel[LAYER_TEXT], TEXT_DRAW_FONT_1);
    TextDrawColor(g_Panel[LAYER_TEXT], 0xFFFFFFFF);
    TextDrawLetterSize(g_Panel[LAYER_TEXT], 0.32, 1.20);
    TextDrawSetOutline(g_Panel[LAYER_TEXT], 1);
    TextDrawBackgroundColor(g_Panel[LAYER_TEXT], 0x00000000);
    TextDrawSetProportional(g_Panel[LAYER_TEXT], true);
}
```

2. Prove the order at boot instead of eyeballing it in game. IDs are comparable as plain cells:

```pawn
stock bool:PanelOrderOk()
{
    new bool:ok = _:g_Panel[LAYER_SHADOW] < _:g_Panel[LAYER_PANEL]
               && _:g_Panel[LAYER_PANEL] < _:g_Panel[LAYER_TEXT];
    printf("[panel] z-order %s shadow=%d panel=%d text=%d", ok ? "OK" : "BROKEN",
           _:g_Panel[LAYER_SHADOW], _:g_Panel[LAYER_PANEL], _:g_Panel[LAYER_TEXT]);
    return ok;
}
```

3. Rebuild the whole panel, never one element. A single destroy/create appends that element to the end of
   the pool, so a re-translated label ends up above its own background:

```pawn
stock PanelRebuild()
{
    for (new layer = 0; layer < LAYER_COUNT; layer++)
    {
        if (g_Panel[layer] != Text:INVALID_TEXT_DRAW) TextDrawDestroy(g_Panel[layer]);
        g_Panel[layer] = Text:INVALID_TEXT_DRAW;
    }
    PanelCreate();          // same order, so the same stacking
    PanelOrderOk();
}
```

4. After the panel exists, only change text in place. `TextDrawSetString` keeps the ID and therefore the
   layer; recreating the draw does not:

```pawn
stock PanelSetTitle(const title[])
{
    TextDrawSetString(g_Panel[LAYER_TEXT], title);
}
```

5. This is the failing version, and it is worth keeping as a comment in the module because it looks
   correct at a glance. The text is created before its background, so the background gets the higher ID
   and paints over the text — showing the text last changes nothing:

```pawn
stock PanelCreateWrong()
{
    new Text:text = TextDrawCreate(112.0, 106.0, "Panel");
    new Text:box  = TextDrawCreate(100.0, 100.0, " ");
    TextDrawUseBox(box, true);
    TextDrawBoxColor(box, 0x000000C8);
    TextDrawTextSize(box, 260.0, 190.0);
    // text is 0, box is 1: the box is drawn second and hides the label
    printf("[panel] wrong order text=%d box=%d", _:text, _:box);
}
```

6. Keep competing elements in one pool. A global draw cannot be lifted above a per-player draw from
   script, so a panel and its tooltip belong to the same pool even if the panel is shared by everyone.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| label vanished after a language switch | label was destroyed and recreated, background was not | rebuild all layers in enum order |
| panel correct at boot, wrong after a filterscript reload | the reload recreated draws at the end of the pool | rebuild every layer of the panel, or reload whole |
| the same panel shows above one player's HUD and below another's | mixed global and per-player elements | move both elements into the per-player pool |
| showing the text last does not help | show order is not a layer | fix creation order |
| `TextDrawSetOutline` used to lift text above a box | outline is inside the draw, not a second draw | add a separate text draw after the box |
| panel and text swap after a long session | elements rebuilt in a different code path | one `PanelCreate`, called from one place |
| IDs march upward on every reopen | destroy/create in a loop without reuse | reuse the handles; rebuild only on layout change |

## Verification

```pawn
// called once from OnGameModeInit
PanelCreate();
PanelRebuild();          // must not change the result
```

```bash
grep "\[panel\] z-order" server.log
```

Expected output, identical before and after the rebuild, which is the whole point of rebuilding in order:

```text
[panel] z-order OK shadow=12 panel=13 text=14
[panel] z-order OK shadow=12 panel=13 text=14
```

Then check the same panel on the two clients you support: the label must stay readable when the panel is
reopened twice, and the IDs in the log must still be ascending.

## Sources (2026)

- https://open.mp/docs/scripting/resources/textdraws
- https://github.com/Knogle/libsamp/blob/main/docs/re/textdraw_render_stack.md
- https://open.mp/docs/scripting/functions/TextDrawSetPos
