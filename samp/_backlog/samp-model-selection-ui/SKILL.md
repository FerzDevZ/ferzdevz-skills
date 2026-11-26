---
name: samp-model-selection-ui
description: Pick skins or vehicles with preview menus.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, ui, models, mselection]
    category: samp
---

# Model selection menus

## When to Use

- A shop, garage or character creator must show models visually, not as a dialog list.
- Players report "the menu opens but every preview is invisible".

## 2026 Compatibility & Architecture Matrix

| Library | State | API |
| --- | --- | --- |
| mSelection (infin1tyy / alextwothousand fork) | maintained, SA-MP 0.3x+ | `LoadModelSelectionMenu`, `ShowModelSelectionMenu`, `ShowModelSelectionMenuEx`, `HideModelSelectionMenu` |
| eSelection | alternative style | own API, do not mix |
| Custom model ids | 0.3.DL / open.mp only | 20001-30000 range |

## Production Implementation

1. Put the list in a file and load it once, not per player:

```pawn
public OnGameModeInit()
{
    LoadModelSelectionMenu("skins.txt");   // one model id per line
    return 1;
}
```

2. Show the menu with explicit colours so it is readable on phones:

```pawn
ShowModelSelectionMenu(playerid, g_SkinList, "Pilih Skin",
    0x121212FF,   // dialog background
    0x2A2A2AFF,   // preview background
    0xFF8C1AFF);  // selection colour
```

3. Required callback: validate the response, never trust the model id:

```pawn
public OnPlayerModelSelection(playerid, response, listid, modelid)
{
    if (!response) return 1;
    if (listid != g_SkinList) return 1;
    if (!IsModelAllowedForPlayer(playerid, modelid)) {
        SendClientMessage(playerid, 0xFF4444FF, "Model tidak tersedia.");
        return 1;
    }
    SetPlayerSkin(playerid, modelid);
    return 1;
}
```

4. Audit the list before shipping:

```bash
python3 ~/.hermes/skills/samp/samp-model-selection-ui/scripts/check_model_list.py scriptfiles/skins.txt
```

## Deprecated Traps & Edge Cases (2026)

- Model id 0 (CJ) looks like "no preview" in some clients; it is valid, test it explicitly.
- Custom ids below 20001 collide with base models; open.mp rejects them silently.
- Showing the menu before `LoadModelSelectionMenu` returns a dead list.
- Calling `ShowModelSelectionMenuEx` with an items array larger than the declared count
  renders blank cells.

## Verification

- Every row in the list has a visible preview on the lowest-end target device.
- `check_model_list.py` exits 0 and reports the count.
- Cancelling the menu leaves the old skin and no stray TextDraw behind.

## Sources (2026)

- https://github.com/alextwothousand/mSelection
- https://open.mp/docs/awesome
