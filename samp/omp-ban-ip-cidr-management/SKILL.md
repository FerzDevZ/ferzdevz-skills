---
name: omp-ban-ip-cidr-management
description: Use when bans expire, leak, or take out a subnet.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, admin, bans, firewall, security]
    category: samp
---

# Bans that survive a restart are rows; subnets are firewall rules

The Pawn ban surface is narrower than admins expect: `Ban`/`BanEx` take a player and
write an IP entry to `bans.json`, `IsBanned` takes an IP string, and `BlockIpAddress`
holds an IP in RAM for a number of milliseconds. None accepts a prefix or can express
"203.0.113.0/24". Account bans and expiry are your table; subnet blocking belongs to
`iptables`/`nftables`/`ufw` on the host, before a player reaches the gamemode.

## When to Use

- A banned player rejoins from the same IP after a restart.
- One offender burns through dynamic IPs and an IP ban does nothing.
- A staff member types a `/16` into an in-game command and locks out a city.
- Bans must carry a reason, an admin and an expiry for appeals.
- Not for connection floods before login — that is `ufw-ddos-raknet-mitigation`.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.6.x | `Ban`, `BanEx`, `IsBanned(ip[])`, RCON `banip`/`unbanip` |
| Ban storage | `bans.json` in the server root | written by the server, not by your gamemode |
| `BlockIpAddress` | RAM only | cleared on restart; accepts octet wildcards such as `203.0.113.*` |
| CIDR support | none in Pawn | no native takes a prefix; host firewall owns subnets |
| Host firewall | ufw 0.36+ / nftables / iptables | `ufw deny from 203.0.113.0/24 to any port 7777 proto udp` |
| Accounts | your MySQL table | the only ban that survives an IP change |

## Production Implementation

1. Model the ban as a row with an expiry, an admin and evidence. An IP column alone
   cannot answer "why is this player banned" later.

```sql
CREATE TABLE bans (
  id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
  account   INT UNSIGNED NULL,
  ip        VARBINARY(16) NULL,          -- INET6_ATON(), works for v4 and v6
  reason    VARCHAR(255) NOT NULL,
  admin     INT UNSIGNED NOT NULL,
  evidence  VARCHAR(255) NULL,
  created   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires   DATETIME NULL,               -- NULL = permanent
  PRIMARY KEY (id),
  KEY b_account (account),
  KEY b_expires (expires)
) ENGINE=InnoDB;
```

2. Check on connect in two independent steps: the account row (survives an IP
   change) and the server's own IP list. `IsBanned` only knows what `bans.json`
   holds, so it cannot replace the table.

```pawn
public OnPlayerConnect(playerid)
{
    new ip[16], q[192];
    GetPlayerIp(playerid, ip, sizeof ip);
    if (IsBanned(ip)) return Kick(playerid);          // bans.json entry
    format(q, sizeof q,
        "SELECT id FROM bans WHERE ip = INET6_ATON('%s') \
         AND (expires IS NULL OR expires > NOW()) LIMIT 1", ip);
    mysql_tquery(g_DB, q, "OnBanChecked", "d", playerid);
    return 1;
}
```

3. Ban in two layers: the game ban for the IP the server sees, and the account row
   for the person. `Ban` closes the connection immediately, so send the reason on a
   short timer first or the player never reads it.

```pawn
stock BanPlayer(playerid, adminid, const reason[], days)
{
    new ip[16], q[320];
    GetPlayerIp(playerid, ip, sizeof ip);
    format(q, sizeof q,
        "INSERT INTO bans (account, ip, reason, admin, evidence, expires) \
         VALUES (%d, INET6_ATON('%s'), '%s', %d, '%s', \
         IF(%d = 0, NULL, NOW() + INTERVAL %d DAY))",
        g_Account[playerid], ip, reason, g_Account[adminid], g_Evidence[adminid],
        days, days);
    mysql_tquery(g_DB, q);                   // row first: it is the durable record
    SendClientMessage(playerid, 0xFF4444FF, reason);
    SetTimerEx("DelayedBan", 1000, false, "d", playerid);
    return 1;
}

forward DelayedBan(playerid);
public DelayedBan(playerid) return Ban(playerid);
```

4. Use `BlockIpAddress` for minutes, never for policy. It is held in memory, takes a
   wildcard per octet rather than a prefix, and disappears on restart — which is
   exactly what you want for an RCON brute force, and wrong for a ban.

```pawn
public OnRconLoginAttempt(ip[], password[], success)
{
    if (!success) BlockIpAddress(ip, 10 * 60 * 1000);
    return 1;
}
```

5. Put subnet rules on the host behind an explicit staff allowlist: a `/24` that
   includes an admin's address locks out the person who can undo it.

```bash
ufw insert 1 allow from 198.51.100.7 to any port 7777 proto udp comment 'staff'
ufw deny from 203.0.113.0/24 to any port 7777 proto udp comment 'ban 2026-01'
ufw status numbered
```

6. Expire bans with a query, not a cron job that edits JSON: a row past `expires` is
   never selected, so the `WHERE` clause is the enforcement.

```sql
SELECT COUNT(*) FROM bans WHERE ip IS NOT NULL AND (expires IS NULL OR expires > NOW());
```

7. Keep `bans.json` from growing forever: permanent rows live in the table, and a
   stale entry is cleared with the documented RCON command (`rcon unbanip 203.0.113.45`)
   rather than by editing the file under a running server.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Ban gone after restart | `BlockIpAddress` used as a ban | `Ban`/`BanEx` plus a DB row |
| Banned player returns on a new IP | IP is the only key | ban the account id, keep the IP row as evidence |
| Admin cannot reconnect after a subnet rule | prefix rule inserted above the allow | staff allow at position 1, then the deny |
| In-game `/banip 203.0.113.0/24` does nothing | no native accepts a prefix | host firewall rule; keep the command for single IPs only |
| `IsBanned` returns false for a banned player | entry lives in the DB, not `bans.json` | check the table on connect as well |
| Ban reason never reaches the player | `Ban` closes the socket before the message flushes | `SetTimerEx` one second, then ban |
| Wildcard block stops working at restart | `BlockIpAddress` is RAM-only | expected; use firewall or `bans.json` for persistence |

## Verification

```bash
ufw status numbered | grep -E '203\.0\.113\.0/24|staff'
mysql -N -B -e "SELECT id, INET6_NTOA(ip), reason, expires FROM samp.bans \
  ORDER BY id DESC LIMIT 3;"
```

```text
[ 1] 7777/udp                   ALLOW IN    198.51.100.7           # staff
[ 3] Anywhere                   DENY IN     203.0.113.0/24         # ban 2026-01
7	203.0.113.45	ban evade	NULL
```

- The allow rule is numbered below the deny, so the admin still connects.
- `ufw --dry-run deny from 203.0.113.0/24 to any port 7777 proto udp` prints the rule
  before you commit it.
- A blocked address times out at the firewall, never reaching `OnPlayerConnect`.

## Sources (2026)

- https://open.mp/docs/scripting/functions/Ban
- https://open.mp/docs/scripting/functions/BlockIpAddress
- https://manpages.ubuntu.com/manpages/noble/en/man8/ufw.8.html
