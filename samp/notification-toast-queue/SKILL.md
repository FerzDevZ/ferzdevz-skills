---
name: notification-toast-queue
description: Use when notices overwrite each other or get missed.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ui, textdraw, notifications]
    category: samp
---

# Toast queue: one overlay, four slots, priorities that survive a burst

## When to Use

- Kills, payouts and admin notices overwrite each other inside the same second.
- A player misses the one message that mattered because three trivia lines landed first.

## Compatibility & Stack Matrix (2026)

| Piece | 2026 reality | What it means here |
| --- | --- | --- |
| Surface | player textdraws, 256 per player | two draws total, not one per message |
| Timer | `SetTimerEx` with `"i"`, one per player, non-empty only | create on first push, `KillTimer` when drained |
| Text | `PlayerTextDrawSetString` accepts format args in open.mp | no manual `format` into a fixed buffer |

## Production Implementation

1. Store a small fixed queue with priority and deadline: a burst cannot allocate, and the cap is a decision, not an accident.

```pawn
#define TOAST_SLOTS      4
#define TOAST_MS         3000
#define TOAST_TICK_MS    250
#define TOAST_PRIO_INFO  1
#define TOAST_PRIO_WARN  2
#define TOAST_PRIO_ERROR 3
enum E_TOAST {
    bool:t_used, t_prio, t_until, t_text[96]
};
new g_Toast[MAX_PLAYERS][TOAST_SLOTS];
new PlayerText:g_ToastBox[MAX_PLAYERS] = { PlayerText:INVALID_TEXT_DRAW, ... };
new PlayerText:g_ToastText[MAX_PLAYERS] = { PlayerText:INVALID_TEXT_DRAW, ... };
new g_ToastTimer[MAX_PLAYERS]; new g_ToastShown[MAX_PLAYERS] = { -1, ... };
```

2. Push coalesces an identical live message instead of stacking it, and when the queue is full it evicts the weakest entry rather than the oldest, so an error never loses to three info lines:

```pawn
stock bool:Toast_Push(playerid, const text[], prio = TOAST_PRIO_INFO, duration = TOAST_MS)
{
    new slot = -1, now = GetTickCount();
    for (new i = 0; i < TOAST_SLOTS; i++)
    {
        if (g_Toast[playerid][i].t_used && !strcmp(g_Toast[playerid][i].t_text, text, false))
            { g_Toast[playerid][i].t_until = now + duration; return true; }   // refresh, no duplicate
        if (slot < 0 && !g_Toast[playerid][i].t_used) slot = i;
    }
    if (slot < 0)
    {
        new worst = 0;
        for (new i = 1; i < TOAST_SLOTS; i++)
            if (g_Toast[playerid][i].t_prio < g_Toast[playerid][worst].t_prio) worst = i;
        if (prio <= g_Toast[playerid][worst].t_prio)
            { printf("[toast] drop player=%d prio=%d text=%s", playerid, prio, text); return false; }
        slot = worst;
    }
    g_Toast[playerid][slot].t_used = true; g_Toast[playerid][slot].t_prio = prio;
    g_Toast[playerid][slot].t_until = now + duration;
    strcat(g_Toast[playerid][slot].t_text, text, 96);
    if (!g_ToastTimer[playerid])
        g_ToastTimer[playerid] = SetTimerEx("Toast_Tick", TOAST_TICK_MS, true, "i", playerid);
    printf("[toast] queue player=%d slot=%d prio=%d", playerid, slot, prio);
    return true;
}
```

3. Build the overlay once per player, on first use, and reuse it for every message. Two draws, one box, one string:

```pawn
stock Toast_Build(playerid)
{
    if (g_ToastBox[playerid] != PlayerText:INVALID_TEXT_DRAW) return 1;
    g_ToastBox[playerid] = CreatePlayerTextDraw(playerid, 320.0, 48.0, " ");
    PlayerTextDrawAlignment(playerid, g_ToastBox[playerid], TEXT_DRAW_ALIGN_CENTER);
    PlayerTextDrawLetterSize(playerid, g_ToastBox[playerid], 0.0, 3.0);
    PlayerTextDrawTextSize(playerid, g_ToastBox[playerid], 300.0, 0.0);
    PlayerTextDrawUseBox(playerid, g_ToastBox[playerid], true);
    PlayerTextDrawBoxColour(playerid, g_ToastBox[playerid], 0x000000B4);
    g_ToastText[playerid] = CreatePlayerTextDraw(playerid, 320.0, 52.0, " ");
    PlayerTextDrawAlignment(playerid, g_ToastText[playerid], TEXT_DRAW_ALIGN_CENTER);
    PlayerTextDrawLetterSize(playerid, g_ToastText[playerid], 0.28, 1.1);
    PlayerTextDrawColour(playerid, g_ToastText[playerid], 0xFFFFFFFF);
    return 1;
}
```

4. Render from one repeating timer per player: retire expired entries, show the highest priority, hide when nothing is live, and stop the timer so an idle player costs zero callbacks:

```pawn
forward Toast_Tick(playerid);
public Toast_Tick(playerid)
{
    if (!IsPlayerConnected(playerid)) { g_ToastTimer[playerid] = 0; return 0; }
    new now = GetTickCount(), best = -1;
    for (new i = 0; i < TOAST_SLOTS; i++)
    {
        if (!g_Toast[playerid][i].t_used) continue;
        if (now >= g_Toast[playerid][i].t_until) { g_Toast[playerid][i].t_used = false; continue; }
        if (best < 0 || g_Toast[playerid][i].t_prio > g_Toast[playerid][best].t_prio) best = i;
    }
    if (best < 0)
    {
        PlayerTextDrawHide(playerid, g_ToastBox[playerid]); PlayerTextDrawHide(playerid, g_ToastText[playerid]);
        KillTimer(g_ToastTimer[playerid]); g_ToastTimer[playerid] = 0; g_ToastShown[playerid] = -1;
        return 0;
    }
    Toast_Build(playerid);
    if (g_ToastShown[playerid] != best) {
        PlayerTextDrawSetString(playerid, g_ToastText[playerid], g_Toast[playerid][best].t_text);
        PlayerTextDrawShow(playerid, g_ToastBox[playerid]); PlayerTextDrawShow(playerid, g_ToastText[playerid]);
        g_ToastShown[playerid] = best;
    }
    return 1;
}
```

5. Clear on death and disconnect, and kill the timer with the player. A repeating timer holding a stale `playerid` writes textdraws to whoever inherits the slot next:

```pawn
public OnPlayerDeath(playerid, killerid, WEAPON:reason)
{
    for (new i = 0; i < TOAST_SLOTS; i++) g_Toast[playerid][i].t_used = false;
    Toast_Tick(playerid); return 1;                          // renders empty and stops the timer
}
public OnPlayerDisconnect(playerid, reason)
{
    if (g_ToastTimer[playerid]) { KillTimer(g_ToastTimer[playerid]); g_ToastTimer[playerid] = 0; }
    if (g_ToastBox[playerid] != PlayerText:INVALID_TEXT_DRAW) PlayerTextDrawDestroy(playerid, g_ToastBox[playerid]);
    if (g_ToastText[playerid] != PlayerText:INVALID_TEXT_DRAW) PlayerTextDrawDestroy(playerid, g_ToastText[playerid]);
    g_ToastBox[playerid] = PlayerText:INVALID_TEXT_DRAW; g_ToastText[playerid] = PlayerText:INVALID_TEXT_DRAW;
    g_ToastShown[playerid] = -1;
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Messages still overwrite | new draw created per message | two draws per player, `SetString` only |
| Timer count grows with players | one `SetTimerEx` per push | create only when `g_ToastTimer` is 0 |
| Toast on the wrong player | timer survived disconnect and the slot was reused | kill the timer in `OnPlayerDisconnect` |
| Error message never seen | full queue evicts by age or drops the new entry | evict the lowest priority, as in step 2 |
| Overlay sticks after death | queue cleared but nothing re-rendered | call `Toast_Tick` after clearing |
## Verification

```bash
pawncc gamemodes/toast.pwn -i include -o /tmp/toast.amx -d3
grep -c 'SetTimerEx("Toast_Tick"' gamemodes/toast.pwn
grep -h '\[toast\]' server_log.txt | tail -20
```

Expected: the compile is clean; the timer count is `1`, proving there is a single creation site rather than one per message; the log shows `[toast] queue` lines with priority 1, 2 and 3 for a three-message burst and at most one `[toast] drop` line when a fourth low-priority message arrives at a full queue. In game the overlay shows one line at a time, the error replaces an info line instead of waiting behind it, and no overlay remains after death or reconnect.

## Sources (2026)

- https://open.mp/docs/scripting/functions/PlayerTextDrawSetString
- https://open.mp/docs/scripting/functions/CreatePlayerTextDraw
- https://open.mp/docs/scripting/functions/SetTimerEx
