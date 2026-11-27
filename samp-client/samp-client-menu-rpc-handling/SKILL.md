---
name: samp-client-menu-rpc-handling
description: Use when ShowMenu RPC never opens or picks wrong row.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, client, cpp, menus, rpc, android]
    category: samp-client
---

# Server menus on the client: three RPCs, one selection

A SA-MP menu is not a dialog. The server initialises it (RPC 76), shows it (77), hides it
(78), and the client answers with a selection or a quit. The pool owns the data, the
overlay owns the pixels; when they disagree the menu draws one thing and reports another.

## When to Use

- `/menu` does nothing on the client while dialogs still work.
- The menu opens but the row you tap is not the row the server receives.
- Titles or rows are truncated, or a two-column menu renders as one column.
- A menu stays on screen after the server hid it or after a disconnect.
- You are adding an RPC that carries pooled state and want the same contract.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Client | samp-client-ferzdevz (C++/JNI, Android) | handlers: `samp/net/scriptrpc.cpp` |
| RPC ids | 76 `RPC_ScrInitMenu`, 77 `RPC_ScrShowMenu`, 78 `RPC_ScrHideMenu` | `samp/vendor/raknet/SAMP/SAMPRPC.cpp` |
| Registration | `RegisterAsRemoteProcedureCall(&RPC_ScrInitMenu, ScrInitMenu)` | all three registered together |
| Pool | `CMenuPool`: `MAX_MENUS 128`, `MAX_MENU_ROWS 12`, `MENU_TEXT_LEN 64` | `samp/net/menupool.h` |
| Pool API | `New(id)`, `GetAt(id)`, `Delete(id)`, `Show(id)`, `Hide(id)`, `TakeSelection()` | no public field writes |
| Rendering | `gui/samp_widgets/menuoverlay.cpp` | sends `RPC_MenuSelect` / `RPC_MenuQuit` |

## Production Implementation

1. Read the wire in this exact order. It is not "id, title, counts": widths and the
   enabled-row bitmap sit between the title and the headers.

```text
u8  menuId
u32 twoColumns            (0 or 1; > 1 is invalid)
str title
f32 posX, posY
f32 col1Width
f32 col2Width             (only when twoColumns == 1)
u32 menuEnabled
bit rowEnabled[12]        (one BIT per row; 12 bits, not 12 bytes)
str col1Header
u8  col1Count             (<= MAX_MENU_ROWS)
u32 col1Len               (<= 12 * MENU_TEXT_LEN)
raw col1 blob (col1Len)
str col2Header, u8 col2Count, u32 col2Len, raw blob   (only when twoColumns == 1)
```

2. Reject before allocating. A bad menu must not consume a slot or half-fill one:

```cpp
uint8_t menuId = 0;
uint32_t twoColumns = 0;
if (!bsData.Read(menuId) || !bsData.Read(twoColumns)) return;
if (twoColumns > 1) { Log("menu %u bad column count", menuId); return; }
...
uint8_t col1Count = 0;
if (!bsData.Read(col1Count)) return;
if (col1Count > MAX_MENU_ROWS) { Log("menu %u asks %u rows", menuId, col1Count); return; }
uint32_t col1Len = 0;
if (!bsData.Read(col1Len)) return;
if (col1Len > 12u * MENU_TEXT_LEN) return;
```

3. Build the slot last, after every field parsed. `New(menuId)` replaces an existing slot,
   so a failed parse leaves the previous menu intact instead of a half-written one.

```cpp
CMenu* menu = pMenuPool->New(menuId);
if (!menu) return;
menu->twoColumns = twoColumns == 1;
menu->posX = pos.x; menu->posY = pos.y;
menu->col1Count = col1Count; menu->col2Count = col2Count;
strncpy(menu->title, title, MENU_TEXT_LEN - 1);
```

4. Cut text with the terminator, never `strcpy`. `MENU_TEXT_LEN - 1` is the only safe copy
   length for a field that is `char[MENU_TEXT_LEN]`.

5. Show and hide are one id each; they never rebuild data:

```cpp
void ScrShowMenu(RPCParameters* rpcParams) { /* read u8 menuId */ pMenuPool->Show(menuId); }
void ScrHideMenu(RPCParameters* rpcParams) { /* read u8 menuId */ pMenuPool->Hide(menuId); }
```

6. The selection travels as the pool's last picked row. The overlay calls `Select(row)`,
   the network path consumes it with `TakeSelection()` and sends `RPC_MenuSelect`; sending
   the row without consuming it double-sends on the next frame.

7. Reset the pool on disconnect and on mode change through one function, so no `shown`
   flag survives a reconnect:

```cpp
void CNetGame::ResetMenuPool()
{
    delete m_pPools->pMenuPool;
    m_pPools->pMenuPool = new CMenuPool();
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Menu never appears, dialogs fine | RPC 76/77/78 not registered, or handler returns early on a read | verify registration and log which read failed |
| Tapped row is off by one | header counted as a data row | rows come from `col1Count`/`col2Count`, headers are not rows |
| Two-column menu shows one column | `twoColumns` read after widths | follow the wire order above exactly |
| Rows missing beyond 12 | server sent more than `MAX_MENU_ROWS` | reject in the handler and log the count |
| Title cut mid-character or crash | `strcpy` into `char[64]` | `strncpy` with `MENU_TEXT_LEN - 1` |
| Old labels for the same menu id | slot reused without `Reset()` | `New(menuId)` replaces the slot; never append |
| Menu visible after disconnect | pool deleted but overlay kept `shown` | rebuild via `ResetMenuPool()`; overlay reads the pool each frame |
| Selection sent twice | `TakeSelection()` not used | consume the selection once, then send |

## Verification

```bash
# the three handlers are registered together
grep -n "RegisterAsRemoteProcedureCall(&RPC_ScrInitMenu" \
  client/app/src/main/cpp/samp/net/scriptrpc.cpp

# the caps are enforced while parsing, not while rendering
grep -n "MAX_MENU_ROWS\|12u \* MENU_TEXT_LEN\|twoColumns > 1" \
  client/app/src/main/cpp/samp/net/scriptrpc.cpp

# runtime: one lifecycle line per menu
adb logcat -s samp | grep -i menu
```

Expected: `ScrInitMenu` logs on `/menu`, `ScrShowMenu` follows, and tapping a row sends one
`RPC_MenuSelect` with the same index the server echoes.

## Sources (2026)

- https://open.mp/docs/scripting/functions/CreateMenu
- https://open.mp/docs/scripting/callbacks/OnPlayerSelectedMenuRow
