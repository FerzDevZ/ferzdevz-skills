---
name: player-report-ticket-system
description: Use when reports vanish in chat and need a queue.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, support, mysql]
    category: samp
---

# Report tickets: one row per report, an explicit state machine

A chat-only `/report` loses the report when nobody is online. Keep a table with a state
column, a cooldown before the insert, and a staff dialog that shows one page.

## When to Use

- Reports arrive as chat spam and nobody can tell which were handled.
- Staff need history per player: who reported whom, when, and what came of it.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | dialogs and commands unchanged from SA-MP |
| MySQL plugin | BlueG MySQL R41-4 | `mysql_tquery` for main-thread callbacks |
| Database | MySQL 8.0 / MariaDB 11.x | `ENUM` state column, InnoDB |

## Production Implementation

1. Create the table with the state machine enforced by the schema, not by comments:

```sql
CREATE TABLE IF NOT EXISTS tickets (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  reporter   VARCHAR(24)  NOT NULL,
  target     VARCHAR(24)  NOT NULL,
  category   TINYINT UNSIGNED NOT NULL,
  body       VARCHAR(180) NOT NULL,
  state      ENUM('open','claimed','closed') NOT NULL DEFAULT 'open',
  assigned   VARCHAR(24) DEFAULT NULL,
  resolution VARCHAR(255) DEFAULT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_state_created (state, created_at),
  KEY idx_target (target, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

2. Validate every field, then insert with `%e` so quotes in free text cannot break the
   statement. The cooldown plus an open-ticket cap stops the dialog-spam loop:

```pawn
#define REPORT_COOLDOWN (120 * 1000)
#define MAX_OPEN_REPORTS (3)
#define DIALOG_TICKETS 9001

new g_LastReport[MAX_PLAYERS], g_OpenReports[MAX_PLAYERS];

CMD:report(playerid, params[])
{
    new targetid, category, body[128];
    if (sscanf(params, "uds[128]", targetid, category, body))
        return SendClientMessage(playerid, 0xFFFFFFFF, "Usage: /report <id> <1-5> <text>");

    if (targetid == playerid || !IsPlayerConnected(targetid))
        return SendClientMessage(playerid, 0xFF0000FF, "Pick another connected player.");
    if (category < 1 || category > 5) return SendClientMessage(playerid, 0xFF0000FF, "Category 1-5.");
    if (strlen(body) < 8) return SendClientMessage(playerid, 0xFF0000FF, "Be specific (8+ chars).");

    if (GetTickCount() - g_LastReport[playerid] < REPORT_COOLDOWN
        || g_OpenReports[playerid] >= MAX_OPEN_REPORTS)
    {
        return SendClientMessage(playerid, 0xFFAA00FF, "Cooldown active or 3 reports already open.");
    }

    g_LastReport[playerid] = GetTickCount();
    g_OpenReports[playerid]++;

    new reporter[24], target[24], query[400];
    GetPlayerName(playerid, reporter, sizeof reporter);
    GetPlayerName(targetid, target, sizeof target);

    mysql_format(gDB, query, sizeof query,
        "INSERT INTO tickets (reporter, target, category, body, state) \
         VALUES ('%e','%e',%d,'%e','open')",
        reporter, target, category, body);
    mysql_tquery(gDB, query);

    SendClientMessage(playerid, 0x00FF00FF, "Report filed. Staff will review it.");
    return 1;
}
```

3. Give staff one page of open tickets, oldest first — a long dialog truncates at the client:

```pawn
CMD:tickets(playerid, params[])
{
    if (!IsPlayerAdmin(playerid)) return SendClientMessage(playerid, 0xFF0000FF, "Admins only.");
    mysql_tquery(gDB,
        "SELECT id, reporter, target, LEFT(body, 60) FROM tickets \
         WHERE state = 'open' ORDER BY created_at ASC LIMIT 20",
        "OnTicketList", "i", playerid);
    return 1;
}

forward OnTicketList(playerid);
public OnTicketList(playerid)
{
    new rows = cache_get_row_count(), line[160], list[20 * 160 + 1];
    if (rows == 0) return SendClientMessage(playerid, 0xFFFFFFFF, "No open tickets.");

    for (new r = 0; r < rows; r++)
    {
        new id, reporter[24], target[24], body[64];
        cache_get_value_name_int(r, "id", id);
        cache_get_value_name(r, "reporter", reporter, sizeof reporter);
        cache_get_value_name(r, "target", target, sizeof target);
        cache_get_value_name(r, "body", body, sizeof body);
        format(line, sizeof line, "#%d %s -> %s | %s\n", id, reporter, target, body);
        strcat(list, line, sizeof list);
    }
    ShowPlayerDialog(playerid, DIALOG_TICKETS, DIALOG_STYLE_LIST, "Open reports", list, "Claim", "Close");
    return 1;
}
```

4. Close only with a resolution note. `claimed` is what stops two admins from working
   the same ticket, and `closed` rows stay forever as the audit trail:

```pawn
stock CloseTicket(ticketid, const admin[], const note[])
{
    if (strlen(note) < 4) return 0;
    new query[320];
    mysql_format(gDB, query, sizeof query,
        "UPDATE tickets SET state = 'closed', assigned = '%e', resolution = '%e' \
         WHERE id = %d AND state <> 'closed'", admin, note, ticketid);
    mysql_tquery(gDB, query);
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| One player fills the queue in a minute | no cooldown, no open-ticket cap | 120 s cooldown plus `MAX_OPEN_REPORTS` |
| Insert fails on an apostrophe in the text | string concatenated into SQL | `%e` in `mysql_format`, never `%s` |
| Staff dialog shows a blank list | `LEFT(body,60)` read with the wrong cache type | read text columns with `cache_get_value_name` |
| Ticket stuck `claimed` after the admin left | no timeout on the claim | reassign on disconnect, or expire claims after 30 min |

## Verification

Apply a burst, then read the state machine in one pass — one row, no empty closure:

```bash
mysql -u samp -p samp -e "SELECT state, COUNT(*) n FROM tickets GROUP BY state;"
mysql -u samp -p samp -e "SELECT id, state, assigned, resolution FROM tickets ORDER BY id DESC LIMIT 5;"
```

Expected after five rapid `/report` calls: exactly `1` open row plus the cooldown message;
after an admin closes it, the row is `closed` with non-null `assigned` and `resolution`.

## Sources (2026)

- https://github.com/pBlueG/SA-MP-MySQL
- https://open.mp/docs/scripting/functions/ShowPlayerDialog
