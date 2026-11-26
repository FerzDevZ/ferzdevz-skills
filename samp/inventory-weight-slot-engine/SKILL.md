---
name: inventory-weight-slot-engine
description: Use when inventory weight or slots can be bypassed.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, gameplay, inventory]
    category: samp
---

# Weight and slots validated in one place, in grams

## When to Use

- An item can be duplicated by dragging it between two slots quickly.
- Weight limits are bypassed by stacking: 200 bandages weigh less than the limit per slot.
- The inventory count does not match what `/give` and `/take` do, or a second UI is being added.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | `DIALOG_STYLE_TABLIST_HEADERS` for the list UI |
| storage | `[MAX_PLAYERS][12]` array | 24 ints per player, no dynamic allocation |
| weight unit | grams (integer) | floats drift; 0.1 kg x 3 is not 0.3 |
| stack cap | per item definition | a global cap makes ammo and bread behave the same |

Slots and weight are independent limits: a light item with `stack = 1` fills the bag, a heavy item with `stack = 100` fits one slot and blows the weight.

## Production Implementation

1. Every tunable lives in the item table; ids are data, never slot positions.
2. Capacity is answered before mutation, and mutations are all-or-nothing.
3. The dialog carries the version. Show the list only after stamping `gDialogVersion[playerid] = gInvVersion[playerid]`, and compare it before touching a slot: a double click is then a rejected stale response, not a free item. Every use path decrements through one branch, then bumps `gInvVersion` and rebuilds the body, so two responses can never apply to the same index.

```pawn
#include <open.mp>

#define INV_SLOTS      (12)
#define INV_MAX_WEIGHT (40000)   // grams
#define INVALID_ITEM   (-1)

enum E_ITEM_DEF { itemId, itemName[28], itemWeight, itemStack };
static const gItemDefs[][E_ITEM_DEF] =
{
    { 1, "Bread", 120, 10 }, { 2, "Water", 500, 5 },
    { 3, "Bandage", 40, 20 }, { 4, "Pistol", 1200, 1 }
};

enum E_INV_SLOT { slotItem, slotQty };
new gInv[MAX_PLAYERS][INV_SLOTS][E_INV_SLOT];
new gInvVersion[MAX_PLAYERS], gDialogVersion[MAX_PLAYERS];

stock ItemIndex(itemid)
{
    for (new i = 0; i < sizeof gItemDefs; i++) if (gItemDefs[i][itemId] == itemid) return i;
    return -1;
}
stock ItemWeight(itemid) { new i = ItemIndex(itemid); return (i == -1) ? 0 : gItemDefs[i][itemWeight]; }
stock ItemStack(itemid)  { new i = ItemIndex(itemid); return (i == -1) ? 0 : gItemDefs[i][itemStack]; }

stock InvWeight(playerid)
{
    new total;
    for (new s = 0; s < INV_SLOTS; s++)
    {
        new item = gInv[playerid][s][slotItem];
        if (item != INVALID_ITEM) total += ItemWeight(item) * gInv[playerid][s][slotQty];
    }
    return total;
}

stock InvSlotsNeeded(playerid, itemid, qty)
{
    new left = qty, stack = ItemStack(itemid), need;
    for (new s = 0; s < INV_SLOTS && left > 0; s++)
        if (gInv[playerid][s][slotItem] == itemid)
        {
            new room = stack - gInv[playerid][s][slotQty];
            if (room > 0) left -= (left < room) ? left : room;
        }
    while (left > 0) { need++; left -= stack; }
    return need;
}

stock InvAdd(playerid, itemid, qty)
{
    if (qty <= 0 || ItemIndex(itemid) == -1) return 0;

    new weight = InvWeight(playerid) + ItemWeight(itemid) * qty, free;
    for (new s = 0; s < INV_SLOTS; s++) if (gInv[playerid][s][slotItem] == INVALID_ITEM) free++;

    if (weight > INV_MAX_WEIGHT)
    {
        printf("[inv] reject weight=%d/%d qty=%d", weight, INV_MAX_WEIGHT, qty);
        return 0;
    }
    if (InvSlotsNeeded(playerid, itemid, qty) > free)
    {
        printf("[inv] reject slots free=%d qty=%d", free, qty);
        return 0;
    }

    new left = qty;
    for (new s = 0; s < INV_SLOTS && left > 0; s++)
    {
        if (gInv[playerid][s][slotItem] != itemid) continue;
        new room = ItemStack(itemid) - gInv[playerid][s][slotQty];
        if (room <= 0) continue;
        new take = (left < room) ? left : room;
        gInv[playerid][s][slotQty] += take;
        left -= take;
    }
    for (new s = 0; s < INV_SLOTS && left > 0; s++)
    {
        if (gInv[playerid][s][slotItem] != INVALID_ITEM) continue;
        new take = (left < ItemStack(itemid)) ? left : ItemStack(itemid);
        gInv[playerid][s][slotItem] = itemid;
        gInv[playerid][s][slotQty]  = take;
        left -= take;
    }
    gInvVersion[playerid]++;
    return qty - left;
}

stock InvMove(playerid, from, to, qty)
{
    if (from < 0 || to < 0 || from >= INV_SLOTS || to >= INV_SLOTS || from == to) return 0;

    new item = gInv[playerid][from][slotItem];
    if (item == INVALID_ITEM || qty <= 0 || qty > gInv[playerid][from][slotQty]) return 0;

    new target = gInv[playerid][to][slotItem];
    if (target != INVALID_ITEM && target != item) return 0;
    if (target == item && gInv[playerid][to][slotQty] + qty > ItemStack(item)) return 0;

    gInv[playerid][from][slotQty] -= qty;
    if (gInv[playerid][from][slotQty] == 0) gInv[playerid][from][slotItem] = INVALID_ITEM;
    gInv[playerid][to][slotItem] = item;
    gInv[playerid][to][slotQty] += qty;
    gInvVersion[playerid]++;
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| item duplicated on a fast double click | two responses applied to the same index | version stamp, reject stale responses |
| heavy item accepted at full weight | only slot count checked | weight checked first, before any mutation |
| move deletes an item | implemented as remove + add with an early failure | one mutation path per direction |
| `/give` bypasses limits | admin command writes slots directly | every write goes through `InvAdd`/`InvMove` |

## Verification

```bash
grep -rn "slotQty\] *[-+]\?=" gamemodes/ | grep -v "gamemodes/inv.inc" | wc -l
```

Expected: `0` — every slot write lives in `inv.inc`, so no command or job can bypass the validators.

Self-test at boot, removed afterwards: `InvAdd(0, 1, 3)` returns `3` and logs nothing; `InvAdd(0, 2, 100)` logs `reject weight=50360/40000` and returns `0`; `InvAdd(0, 4, 13)` logs `reject slots free=11 qty=13` and returns `0`; `InvMove(0, 0, 5, 2)` returns `1`. Weight after the first call is 360 g in one slot.

## Sources (2026)

- [open.mp — OnDialogResponse](https://open.mp/docs/scripting/callbacks/OnDialogResponse) — `listitem` semantics and the stale-dialog warning.
- [sscanf 2.15.1 include](https://raw.githubusercontent.com/maddinat0r/sscanf/master/sscanf2.inc) — specifier behaviour and non-zero return on parse failure.
