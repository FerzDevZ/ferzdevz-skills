---
name: samp-third-party-anticheat-integration
description: Use when a second anticheat must not double-ban.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, anticheat, security, integration, bans]
    category: samp
---

# One ban authority: run the community AC as a sensor, not a judge

Two anticheats that both ban produce two records for one cheat, and the second write
usually destroys the first one's evidence. The rule is structural: the third-party AC
reports a verdict, exactly one module decides, and both evidence sets are stored first.

## When to Use

- Adding Nex-AC, SAMP_AC_v2 or a Pawn anticheat on top of existing server-side checks.
- The same player shows two ban entries with different reasons.
- You need to keep the third-party AC's own reason string for appeals.
- Not for new checks — those live in `weapon-ammo-desync-anticheat`,
  `teleport-airbreak-detection` and `fake-kill-bullet-crasher-shield`.

## Compatibility & Stack Matrix (2026)

| Project | Type | Note |
| --- | --- | --- |
| Nex-AC (`nexiustailer/nex-ac`) | Pawn anticheat | runs inside the gamemode; fork for open.mp includes |
| SAMP_AC_v2 (`Whitetigerswt`) | client plugin + server script | client plugin only reaches PC clients |
| open.mp server | 1.6.7.3218 | `BanEx`, `Kick`, `OnPlayerUpdate` unchanged |
| Your policy module | one file, one ban function | the only place `BanEx` may appear |

## Production Implementation

1. Audit the AC before it loads — what it hooks tells you whether it can coexist:

```bash
grep -nE "OnPlayerUpdate|Ban|BanEx|Kick|SetTimer" ac/*.pwn | head -40
grep -rn "public OnPlayerUpdate" gamemodes/ ac/ | wc -l
```

A duplicate `public OnPlayerUpdate` is only safe under `y_hooks`; a plain second
definition silently replaces the first.

2. Create the evidence tables first. The unique key is the dedupe: one subject, one
   cheat, one 10-minute bucket cannot produce two ban rows, while `ac_evidence` stays a
   plain append-only log:

```sql
CREATE TABLE IF NOT EXISTS ac_evidence (
  id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  subject VARCHAR(24) NOT NULL,
  ip      VARCHAR(16) NOT NULL,
  cheat   VARCHAR(48) NOT NULL,
  source  VARCHAR(32) NOT NULL,
  detail  TEXT NOT NULL,
  seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_subject_seen (subject, seen_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ac_bans (
  id      BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  subject VARCHAR(24) NOT NULL,
  ip      VARCHAR(16) NOT NULL,
  cheat   VARCHAR(48) NOT NULL,
  source  VARCHAR(32) NOT NULL,
  detail  TEXT NOT NULL,
  bucket  INT UNSIGNED NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uniq_subject_cheat_bucket (subject, cheat, bucket)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

3. Route every verdict through one function: it records first, dedupes second, applies
   the ban last, so a crash never leaves a ban without evidence:

```pawn
new bool:g_Banned[MAX_PLAYERS];

stock AcVerdict(playerid, const source[], const cheat[], const detail[])
{
    if (playerid == INVALID_PLAYER_ID || g_Banned[playerid]) return 0;

    new name[24], ip[16], query[512];
    GetPlayerName(playerid, name, sizeof name);
    GetPlayerIp(playerid, ip, sizeof ip);

    mysql_format(gDB, query, sizeof query,
        "INSERT INTO ac_evidence (subject, ip, cheat, source, detail) \
         VALUES ('%e','%e','%e','%e','%e')",
        name, ip, cheat, source, detail);
    mysql_tquery(gDB, query);

    mysql_format(gDB, query, sizeof query,
        "INSERT INTO ac_bans (subject, ip, cheat, source, detail, bucket) \
         VALUES ('%e','%e','%e','%e','%e', UNIX_TIMESTAMP() DIV 600) \
         ON DUPLICATE KEY UPDATE detail = CONCAT(ac_bans.detail, '\n', VALUES(detail))",
        name, ip, cheat, source, detail);
    mysql_tquery(gDB, query);

    g_Banned[playerid] = true;
    printf("[AC] ban %s source=%s cheat=%s", name, source, cheat);
    BanEx(playerid, cheat);
    return 1;
}
```

4. Wire the community AC in as a source. The AC's own reason string is passed through
   untouched — that is the "keep the other system's evidence" part; never re-word it:

```pawn
// adapter callback the community AC is pointed at
public OnAnticheatDetect(playerid, const reason[])
{
    new detail[160];
    format(detail, sizeof detail, "pos %.1f %.1f %.1f weapon %d ping %d",
           g_LastX[playerid], g_LastY[playerid], g_LastZ[playerid],
           GetPlayerWeapon(playerid), GetPlayerPing(playerid));
    return AcVerdict(playerid, "community-ac", reason, detail);
}
```

5. Turn the AC's own kick/ban action off in its config or include and keep only its
   detection (`grep -rn "ac_enable\|AC_BAN" ac/`). If a build has no report-only switch,
   make the AC the ban authority and demote your checks to warn-only — one owner, never two.

6. Gate economy and inventory actions on server-side checks only. A client-plugin AC
   cannot see Android clients at all, so anything it "protects" is unprotected there.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Two ban rows, second reason replaces the first | both ACs call `BanEx` | one authority: AC reports, policy bans |
| Evidence lost on appeal | `UPDATE ... SET reason =` overwrite | append-only rows, `CONCAT` on duplicate |
| Your `OnPlayerUpdate` stopped running | AC defines a duplicate public | merge under `y_hooks`, or drop one |
| Android players cheat freely | client plugin never loads on mobile | server-side invariants are the real check |
| Same cheat logged 20 times in 5 s | no dedupe window | unique key on subject+cheat+bucket |

## Verification

Prove there is exactly one ban authority — this must print nothing outside the policy
file:

```bash
grep -rnE "\b(BanEx|Ban)\s*\(" gamemodes/ ac/ | grep -v "ac_policy.pwn"
```

Then trigger one cheat from a test account and read the store: one row per table, both
sources present:

```bash
mysql -u samp -p samp -e \
  "SELECT subject, cheat, source, COUNT(*) n FROM ac_evidence GROUP BY subject, cheat, source;"
mysql -u samp -p samp -e \
  "SELECT subject, cheat, source, detail FROM ac_bans ORDER BY id DESC LIMIT 3;"
```

Expected: a single `ac_bans` row for the test subject whose `detail` contains both the
community AC's reason text and your position/weapon line. Record the tick average before
and after install with the profiler — a number, not an assumption.

## Sources (2026)

- https://github.com/nexiustailer/nex-ac
- https://github.com/Whitetigerswt/SAMP_AC_v2
- https://open.mp/docs/scripting/functions/BanEx
