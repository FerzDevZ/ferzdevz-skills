---
name: dialog-spoofing-validation
description: Use when forged dialog responses bypass the UI.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, security, ui]
    category: samp
---

# Dialog responses: bind every answer to a dialog you opened

## When to Use

- A shop purchase completes without the buyer ever opening the shop.
- A house or vehicle id from `listitem` is used directly and points at someone else's property.
- Players report "I clicked Cancel and it charged me" — the client can send either button.
- For flooding rather than forging, use `raknet-incoming-rpc-filter` first.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.4.x 2026 builds | `GetPlayerDialogID` replaced the deprecated `GetPlayerDialog` |
| SA-MP server | 0.3.7-R5, 0.3.DL-R1 | no `GetPlayerDialogID`, keep your own pending id |
| pawncc | 3.10.11 or newer | `-d3`; a 213 on `listitem` usually means a tag came back |

## Production Implementation

1. Note the documented contract before writing rules: a response is `dialogid`, `response` (`1` = left button or ENTER, `0` = right button or ESC), `listitem` (`-1` for every non-list style) and `inputtext`. open.mp defines no `DIALOG_RESPONSE_*` constants, so name them yourself and never accept a third value:

```pawn
#define DIALOG_RESPONSE_LEFT   1
#define DIALOG_RESPONSE_RIGHT  0

enum E_Dlg { dlgId, dlgSeq, dlgShop, dlgTick };
new g_Dlg[MAX_PLAYERS][E_Dlg];
```

2. Record the pending dialog server-side at show time. `ShowPlayerDialog` is synchronous, so close whatever is open first, otherwise the old context leaks into the new answer:

```pawn
stock ShowShopDialog(playerid, shopid)
{
    new body[1024];
    BuildShopBody(shopid, body, sizeof body);          // server-side item list, in order

    if (GetPlayerDialogID(playerid) != INVALID_DIALOG_ID) HidePlayerDialog(playerid);

    g_Dlg[playerid][dlgId]   = DIALOG_SHOP;
    g_Dlg[playerid][dlgSeq]++;
    g_Dlg[playerid][dlgShop] = shopid;
    g_Dlg[playerid][dlgTick] = GetTickCount();
    ShowPlayerDialog(playerid, DIALOG_SHOP, DIALOG_STYLE_LIST, "Shop", body, "Buy", "Close");
    return 1;
}
```

3. Reject anything that does not match the pending context before you read `listitem` as an index:

```pawn
public OnDialogResponse(playerid, dialogid, response, listitem, inputtext[])
{
    if (dialogid == 0 || dialogid != g_Dlg[playerid][dlgId])
        return RejectDialog(playerid, dialogid, response, listitem, "id_mismatch");

    if (response != DIALOG_RESPONSE_LEFT && response != DIALOG_RESPONSE_RIGHT)
        return RejectDialog(playerid, dialogid, response, listitem, "bad_response");

    if (g_Dlg[playerid][dlgTick] + 120000 < GetTickCount())      // stale after two minutes
        return RejectDialog(playerid, dialogid, response, listitem, "stale_state");

    if (GetPlayerState(playerid) != PLAYER_STATE_ONFOOT
        || !IsPlayerInRangeOfPoint(playerid, 5.0, g_ShopX[g_Dlg[playerid][dlgShop]],
            g_ShopY[g_Dlg[playerid][dlgShop]], g_ShopZ[g_Dlg[playerid][dlgShop]]))
        return RejectDialog(playerid, dialogid, response, listitem, "out_of_context");

    if (response == DIALOG_RESPONSE_RIGHT) return CloseDialogContext(playerid, "cancel");
    return HandleShopBuy(playerid, g_Dlg[playerid][dlgShop], listitem);
}
```

4. Map `listitem` through the same server array that built the body, range-check it, and re-read price and stock at confirm time. Consume the context on every exit path so one dialog can be answered once:

```pawn
stock CloseDialogContext(playerid, const reason[])
{
    g_Dlg[playerid][dlgId] = 0, g_Dlg[playerid][dlgShop] = -1;
    printf("dlg_close pid=%d reason=%s seq=%d", playerid, reason, g_Dlg[playerid][dlgSeq]);
    return 1;
}

stock HandleShopBuy(playerid, shopid, listitem)
{
    if (listitem < 0 || listitem >= g_ShopCount[shopid])
        return RejectDialog(playerid, DIALOG_SHOP, DIALOG_RESPONSE_LEFT, listitem, "index_out_of_range");

    new itemid = g_ShopItem[shopid][listitem];         // listitem -> server item id
    if (g_ShopStock[shopid][itemid] <= 0) return CloseDialogContext(playerid, "out_of_stock");
    if (GetPlayerMoney(playerid) < g_ShopPrice[itemid]) return CloseDialogContext(playerid, "no_money");

    g_ShopStock[shopid][itemid]--;
    GivePlayerMoney(playerid, -g_ShopPrice[itemid]);
    return CloseDialogContext(playerid, "bought");
}
```

5. Log the rejection with the id the client claimed, the id you expected and the raw list index, then escalate only on repetition — one mismatch is usually a double-click race:

```pawn
new g_DlgRejects[MAX_PLAYERS], g_DlgRejectSecond[MAX_PLAYERS];

stock RejectDialog(playerid, dialogid, response, listitem, const reason[])
{
    new sec = GetTickCount() / 1000, line[192], name[MAX_PLAYER_NAME + 1], File:f;
    if (g_DlgRejectSecond[playerid] != sec) g_DlgRejectSecond[playerid] = sec, g_DlgRejects[playerid] = 0;
    g_DlgRejects[playerid]++;

    GetPlayerName(playerid, name, sizeof name);
    if ((f = fopen("ac/dialog.log", io_append)))
    {
        format(line, sizeof line, "DIALOG_REJECT|%d|%d|%d|%d|%d|%s|%s\n", playerid, dialogid,
            g_Dlg[playerid][dlgId], response, listitem, reason, name);
        fwrite(f, line);
        fclose(f);
    }
    CloseDialogContext(playerid, reason);
    if (g_DlgRejects[playerid] > 10) Kick(playerid);           // 10 in one second
    return 0;
}
```

6. Read the log before banning and retain it 30 days (`find scriptfiles/ac -name 'dialog.log*' -mtime +30 -delete`); a ban without the claimed id, the expected id and the timestamp is not defensible.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Legit players kicked on fast clicks | kick threshold counts every mismatch | clear the counter per second and raise the kick limit |
| A cancelled dialog still charges | only the left button branch was handled | handle `DIALOG_RESPONSE_RIGHT` explicitly and consume the context |
| Same dialog answered twice | context not cleared after accept | `CloseDialogContext` on every exit path |

## Verification

```bash
./pawncc gamemodes/main.pwn -d3 -o gamemodes/main.amx
python3 - <<'PY'
import collections
rows = [l.strip().split("|") for l in open("scriptfiles/ac/dialog.log") if l.startswith("DIALOG_REJECT")]
print("rejects", len(rows), "by_player", dict(collections.Counter(r[1] for r in rows).most_common()))
print("reasons", dict(collections.Counter(r[6] for r in rows)))
PY
```

Expected output after one spoofing client and one stale dialog:

```text
rejects 4 by_player {'3': 2, '8': 2}
reasons {'id_mismatch': 2, 'index_out_of_range': 1, 'stale_state': 1}
```

- Manual: RPC `62` with a dialog id you never opened logs `id_mismatch`; opening the shop, walking 20 m away and answering logs `out_of_context`. No money moves in either case.

## Sources (2026)

- https://open.mp/docs/scripting/callbacks/OnDialogResponse — response is 1 for the left button and 0 for the right, listitem is -1 for non-list styles.
- https://open.mp/docs/scripting/functions/GetPlayerDialogID — returns `INVALID_DIALOG_ID` when nothing is open; replaces the deprecated `GetPlayerDialog`.
- https://github.com/Brunoo16/samp-packet-list/wiki/RPC-List — incoming RPC 62 `DialogResponse` field order.
